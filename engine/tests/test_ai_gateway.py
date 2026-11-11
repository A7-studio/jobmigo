"""Ports of web/tests/ai-gateway.test.ts (each test names its source case)."""

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal

import pytest
from pydantic import BaseModel, Field

from engine.ai.errors import (
    AiInputInvalidError,
    AiNotConfiguredError,
    AiOutputInvalidError,
    AiUnavailableError,
)
from engine.ai.gateway import cache_key_for, canonical_json, run_task
from engine.ai.provider import AiRequest, AiResponse
from engine.ai.tasks import AiTask
from engine.db import Database
from tests.db import fetch, upgrade

ENV = {
    "AI_CHEAP_MODEL": "deepseek/model-a",
    "AI_CHEAP_PRICE": "1,2",
    "DEEPSEEK_API_KEY": "test-key",
}


class Fake:
    """A provider that answers from a queue and remembers every request."""

    name = "fake"

    def __init__(self, *queue: AiResponse | Exception) -> None:
        self.queue = list(queue)
        self.calls: list[AiRequest] = []

    async def complete(self, request: AiRequest) -> AiResponse:
        self.calls.append(request)
        if not self.queue:
            raise RuntimeError("no response queued")
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def reply(text: str, tokens_in: int = 100, tokens_out: int = 50) -> AiResponse:
    return AiResponse(text, tokens_in, tokens_out)


class In(BaseModel):
    text: str = Field(min_length=1)


class Out(BaseModel):
    name: str


TASK: AiTask[In, Out] = AiTask(
    name="demo-parse",
    workflow="parse",
    tier="cheap",
    prompt_version="v1",
    system="Extract the name.",
    user=lambda i: f"Text: {i.text}",
    input_model=In,
    output_model=Out,
)


@pytest.fixture
async def database(db_url: str) -> AsyncIterator[Database]:
    await upgrade(db_url)
    db = Database(db_url)
    yield db
    await db.dispose()


async def events(db_url: str, user: uuid.UUID) -> list[dict[str, object]]:
    return await fetch(
        db_url,
        "select * from engine.usage_event where user_id = $1 order by created_at",
        user,
    )


async def cache_rows(db_url: str) -> list[dict[str, object]]:
    return await fetch(db_url, "select * from engine.ai_cache")


def test_canonical_hashing_ignores_key_order_and_differs_on_content() -> None:
    # canonical hashing: 'ignores key order and differs on content'
    assert canonical_json({"b": 1, "a": {"d": 2, "c": 3}}) == canonical_json(
        {"a": {"c": 3, "d": 2}, "b": 1}
    )
    assert cache_key_for("t", "v1", "p/m", {"a": 1}) != cache_key_for(
        "t", "v1", "p/m", {"a": 2}
    )


def test_the_task_definition_keeps_what_was_written() -> None:
    # defineTask: 'keeps the definition as written'
    assert TASK.prompt_version == "v1"
    assert TASK.cache is True
    assert TASK.timeout_s is None


async def test_calls_the_model_writes_one_usage_event_and_caches_the_output(
    database: Database, db_url: str
) -> None:
    # 'calls the model, writes one usage event, and caches the output'
    user = uuid.uuid4()
    provider = Fake(reply('{"name":"Ada"}', 1000, 500))
    result = await run_task(
        TASK,
        {"text": "hello"},
        user_id=user,
        database=database,
        env=ENV,
        provider=provider,
    )
    assert result.output == Out(name="Ada")
    assert result.cache_hit is False
    assert result.prompt_version == "v1"
    assert len(provider.calls) == 1
    assert provider.calls[0].model == "model-a"
    assert "single JSON object" in provider.calls[0].system
    rows = await events(db_url, user)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == result.usage_event_id
    assert (row["workflow"], row["provider"], row["model"]) == (
        "parse",
        "deepseek",
        "model-a",
    )
    assert (row["prompt_version"], row["tokens_in"], row["tokens_out"]) == (
        "v1",
        1000,
        500,
    )
    assert row["cache_hit"] is False
    assert row["cost_usd"] == Decimal("0.002")
    assert len(await cache_rows(db_url)) == 1


async def test_serves_the_same_input_from_the_cache_with_no_provider_call(
    database: Database, db_url: str
) -> None:
    # 'serves the same input from the cache with no provider call'
    user = uuid.uuid4()
    await run_task(
        TASK,
        {"text": "hello"},
        user_id=user,
        database=database,
        env=ENV,
        provider=Fake(reply('{"name":"Ada"}')),
    )
    second = Fake()
    hit = await run_task(
        TASK,
        {"text": "hello"},
        user_id=user,
        database=database,
        env=ENV,
        provider=second,
    )
    assert hit.cache_hit is True
    assert hit.output == Out(name="Ada")
    assert second.calls == []
    rows = await events(db_url, user)
    assert len(rows) == 2
    cached = next(row for row in rows if row["cache_hit"])
    assert (cached["tokens_in"], cached["tokens_out"]) == (0, 0)
    assert cached["cost_usd"] == Decimal(0)


async def test_never_serves_one_user_the_cache_of_another(database: Database) -> None:
    # 'never serves one user the cache of another'
    alice, bob = uuid.uuid4(), uuid.uuid4()
    await run_task(
        TASK,
        {"text": "same"},
        user_id=alice,
        database=database,
        env=ENV,
        provider=Fake(reply('{"name":"Alice"}')),
    )
    provider = Fake(reply('{"name":"Bob"}'))
    result = await run_task(
        TASK,
        {"text": "same"},
        user_id=bob,
        database=database,
        env=ENV,
        provider=provider,
    )
    assert result.cache_hit is False
    assert result.output == Out(name="Bob")
    assert len(provider.calls) == 1


async def test_misses_when_the_prompt_version_or_the_model_changes(
    database: Database,
) -> None:
    # 'misses when the prompt version or the model changes'
    user = uuid.uuid4()
    await run_task(
        TASK,
        {"text": "x"},
        user_id=user,
        database=database,
        env=ENV,
        provider=Fake(reply('{"name":"A"}')),
    )
    bumped = replace(TASK, prompt_version="v2")
    second = await run_task(
        bumped,
        {"text": "x"},
        user_id=user,
        database=database,
        env=ENV,
        provider=Fake(reply('{"name":"B"}')),
    )
    assert second.cache_hit is False
    third_provider = Fake(reply('{"name":"C"}'))
    third = await run_task(
        TASK,
        {"text": "x"},
        user_id=user,
        database=database,
        env={**ENV, "AI_CHEAP_MODEL": "deepseek/model-b"},
        provider=third_provider,
    )
    assert third.cache_hit is False
    assert len(third_provider.calls) == 1


async def test_retries_once_on_invalid_output_and_records_both_calls(
    database: Database, db_url: str
) -> None:
    # 'retries once on invalid output and records both calls'
    user = uuid.uuid4()
    provider = Fake(reply("not json at all", 10, 5), reply('{"name":"Ada"}', 20, 8))
    result = await run_task(
        TASK,
        {"text": "hello"},
        user_id=user,
        database=database,
        env=ENV,
        provider=provider,
    )
    assert result.output == Out(name="Ada")
    assert len(provider.calls) == 2
    assert "previous reply was rejected" in provider.calls[1].user
    assert "not json at all" not in provider.calls[1].user
    assert len(await events(db_url, user)) == 2
    outcomes = await fetch(
        db_url,
        "select outcome from engine.usage_event where user_id = $1 order by created_at",
        user,
    )
    assert [r["outcome"] for r in outcomes] == ["rejected", "ok"]


async def test_fails_visibly_after_a_second_invalid_output_and_caches_nothing(
    database: Database, db_url: str
) -> None:
    # 'fails visibly after a second invalid output and caches nothing'
    user = uuid.uuid4()
    provider = Fake(reply('{"wrong":1}'), reply('{"name":42}'))
    with pytest.raises(AiOutputInvalidError) as caught:
        await run_task(
            TASK,
            {"text": "hello"},
            user_id=user,
            database=database,
            env=ENV,
            provider=provider,
        )
    assert caught.value.code == "ai_output_invalid"
    assert len(await events(db_url, user)) == 2
    both = await fetch(
        db_url, "select outcome from engine.usage_event where user_id = $1", user
    )
    assert [r["outcome"] for r in both] == ["rejected", "rejected"]
    assert await cache_rows(db_url) == []


async def test_throws_ai_unavailable_and_records_one_failed_row_when_the_provider_fails(
    database: Database, db_url: str
) -> None:
    # 'throws ai_unavailable and records one failed row when the provider fails'
    user = uuid.uuid4()
    with pytest.raises(AiUnavailableError):
        await run_task(
            TASK,
            {"text": "hello"},
            user_id=user,
            database=database,
            env=ENV,
            provider=Fake(AiUnavailableError()),
        )
    rows = await fetch(
        db_url,
        "select outcome, tokens_in, tokens_out from engine.usage_event"
        " where user_id = $1",
        user,
    )
    assert [(r["outcome"], r["tokens_in"], r["tokens_out"]) for r in rows] == [
        ("failed", 0, 0)
    ]


async def test_rejects_invalid_input_before_any_provider_call(
    database: Database, db_url: str
) -> None:
    # 'rejects invalid input before any provider call'
    user = uuid.uuid4()
    provider = Fake()
    with pytest.raises(AiInputInvalidError) as caught:
        await run_task(
            TASK,
            {"text": ""},
            user_id=user,
            database=database,
            env=ENV,
            provider=provider,
        )
    assert caught.value.status == 400
    assert provider.calls == []
    assert await events(db_url, user) == []


async def test_fails_before_any_call_when_the_tier_is_not_configured(
    database: Database,
) -> None:
    # 'fails before any call when the tier is not configured'
    provider = Fake()
    with pytest.raises(AiNotConfiguredError):
        await run_task(
            TASK,
            {"text": "hello"},
            user_id=uuid.uuid4(),
            database=database,
            env={},
            provider=provider,
        )
    assert provider.calls == []


async def test_treats_a_cached_value_that_no_longer_fits_the_schema_as_a_miss(
    database: Database, db_url: str
) -> None:
    # 'treats a cached value that no longer fits the schema as a miss'
    user = uuid.uuid4()
    key = cache_key_for("demo-parse", "v1", "deepseek/model-a", {"text": "hello"})
    await fetch(
        db_url,
        "insert into engine.ai_cache "
        "(user_id, cache_key, task, prompt_version, output) "
        "values ($1, $2, 'demo-parse', 'v1', '{\"shape\": \"old\"}'::jsonb) "
        "returning 1",
        user,
        key,
    )
    result = await run_task(
        TASK,
        {"text": "hello"},
        user_id=user,
        database=database,
        env=ENV,
        provider=Fake(reply('{"name":"Fresh"}')),
    )
    assert result.cache_hit is False
    assert result.output == Out(name="Fresh")
    rows = await cache_rows(db_url)
    assert len(rows) == 1
    assert rows[0]["output"] == '{"name": "Fresh"}'


async def test_records_a_billed_reply_that_has_no_content_then_retries(
    database: Database, db_url: str
) -> None:
    # 'records a billed reply that has no content, then retries'
    user = uuid.uuid4()
    provider = Fake(reply("", 30, 0), reply('{"name":"Ada"}', 20, 8))
    result = await run_task(
        TASK,
        {"text": "hello"},
        user_id=user,
        database=database,
        env=ENV,
        provider=provider,
    )
    assert result.output == Out(name="Ada")
    rows = await events(db_url, user)
    assert sorted(int(str(row["tokens_in"])) for row in rows) == [20, 30]


async def test_passes_the_task_time_limit_to_the_provider(database: Database) -> None:
    # 'passes the task time limit to the provider'
    slow = replace(TASK, name="slow", timeout_s=1.234)
    provider = Fake(reply('{"name":"Ada"}'))
    await run_task(
        slow,
        {"text": "x"},
        user_id=uuid.uuid4(),
        database=database,
        env=ENV,
        provider=provider,
    )
    assert provider.calls[0].timeout_s == 1.234


async def test_records_a_null_cost_when_no_price_is_configured(
    database: Database, db_url: str
) -> None:
    # 'records a null cost when no price is configured'
    user = uuid.uuid4()
    await run_task(
        TASK,
        {"text": "hello"},
        user_id=user,
        database=database,
        env={"AI_CHEAP_MODEL": "deepseek/model-a"},
        provider=Fake(reply('{"name":"Ada"}')),
    )
    assert (await events(db_url, user))[0]["cost_usd"] is None


async def test_skips_the_cache_for_tasks_that_opt_out(
    database: Database, db_url: str
) -> None:
    # 'skips the cache for tasks that opt out'
    user = uuid.uuid4()
    fresh = replace(TASK, name="no-cache", cache=False)
    provider = Fake(reply('{"name":"One"}'), reply('{"name":"Two"}'))
    await run_task(
        fresh,
        {"text": "x"},
        user_id=user,
        database=database,
        env=ENV,
        provider=provider,
    )
    second = await run_task(
        fresh,
        {"text": "x"},
        user_id=user,
        database=database,
        env=ENV,
        provider=provider,
    )
    assert second.cache_hit is False
    assert second.output == Out(name="Two")
    assert await cache_rows(db_url) == []


async def test_never_logs_the_input_or_the_model_output(
    database: Database, caplog: pytest.LogCaptureFixture
) -> None:
    # 'never logs the input or the model output'
    caplog.set_level(logging.DEBUG, logger="engine")
    await run_task(
        TASK,
        {"text": "cv-secret-text"},
        user_id=uuid.uuid4(),
        database=database,
        env=ENV,
        provider=Fake(reply("garbage reply-secret"), reply('{"name":"output-secret"}')),
    )
    logged = "\n".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    assert "ai task" in logged
    for secret in ("cv-secret-text", "reply-secret", "output-secret", "test-key"):
        assert secret not in logged


async def test_a_failed_cache_write_keeps_the_paid_answer_and_logs_no_content(
    database: Database,
    db_url: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # open finding F-47: the cache is an optimisation, never a reason to lose a reply
    def broken(*_: object, **__: object) -> object:
        raise RuntimeError("Failed query: params: output-secret")

    monkeypatch.setattr("engine.ai.gateway.insert", broken)
    caplog.set_level(logging.DEBUG, logger="engine")
    user = uuid.uuid4()
    result = await run_task(
        TASK,
        {"text": "hello"},
        user_id=user,
        database=database,
        env=ENV,
        provider=Fake(reply('{"name":"output-secret"}')),
    )
    assert result.output == Out(name="output-secret")
    assert len(await events(db_url, user)) == 1
    logged = "\n".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    assert "ai_cache_write_failed" in logged
    assert "output-secret" not in logged


class Measure(BaseModel):
    value: float


async def test_an_input_that_cannot_be_hashed_exactly_is_rejected(
    database: Database,
) -> None:
    # open finding F-42: NaN must never collapse onto another input's cache key
    task: AiTask[Measure, Out] = AiTask(
        name="measure",
        workflow="parse",
        tier="cheap",
        prompt_version="v1",
        system="s",
        user=lambda i: "x",
        input_model=Measure,
        output_model=Out,
    )
    with pytest.raises(AiInputInvalidError):
        await run_task(
            task,
            {"value": float("nan")},
            user_id=uuid.uuid4(),
            database=database,
            env=ENV,
            provider=Fake(),
        )
