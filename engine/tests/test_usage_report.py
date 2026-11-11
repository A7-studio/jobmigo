"""The AI usage report: counts, money, failures, cache savings and the paid estimate."""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import asyncpg
import pytest
from fastapi import FastAPI

from engine.ai.usage_report import usage_report
from engine.config import Settings
from engine.db import Database
from engine.main import create_app
from tests.conftest import TOKEN
from tests.db import upgrade
from tests.test_cv_routes import USER_A, auth, http


@pytest.fixture
async def database(db_url: str) -> AsyncIterator[Database]:
    await upgrade(db_url)
    db = Database(db_url)
    yield db
    await db.dispose()


async def put(
    url: str,
    *,
    workflow: str = "evaluate",
    model: str = "m1",
    version: str = "v1",
    tokens_in: int = 1000,
    tokens_out: int = 500,
    cost: str | None = "0.010000",
    cache: bool = False,
    outcome: str = "ok",
    when: datetime | None = None,
    user: uuid.UUID | None = None,
) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(
            "insert into engine.usage_event (user_id, workflow, provider, model,"
            " prompt_version, tokens_in, tokens_out, cost_usd, cache_hit, outcome,"
            " created_at) values ($1,$2,'p',$3,$4,$5,$6,$7,$8,$9,$10)",
            user or uuid.uuid4(),
            workflow,
            model,
            version,
            tokens_in,
            tokens_out,
            Decimal(cost) if cost is not None else None,
            cache,
            outcome,
            when or datetime.now(UTC),
        )
    finally:
        await connection.close()


async def test_an_empty_ledger_gives_an_empty_report(database: Database) -> None:
    report = await usage_report(database, env={})
    assert report.rows == [] and report.workflows == []
    assert report.total_cost_usd == 0
    assert report.compare.configured is False
    assert report.golden_set is None


async def test_adds_up_calls_tokens_cost_and_failures_per_workflow(
    database: Database, db_url: str
) -> None:
    await put(db_url)
    await put(db_url, cost="0.020000", user=uuid.uuid4())
    await put(db_url, outcome="rejected", cost="0.010000")
    await put(db_url, outcome="failed", tokens_in=0, tokens_out=0, cost="0")
    await put(db_url, workflow="screen", cost="0.001000")
    report = await usage_report(database, env={})
    by = {w.workflow: w for w in report.workflows}
    ev = by["evaluate"]
    assert (ev.calls, ev.rejected, ev.failed, ev.cache_hits) == (4, 1, 1, 0)
    assert ev.tokens_in == 3000 and ev.tokens_out == 1500
    assert ev.cost_usd == Decimal("0.040000")
    # the average counts only calls that gave a usable answer and had a price
    assert ev.avg_cost_usd == Decimal("0.015000")
    assert by["screen"].calls == 1
    assert report.total_cost_usd == Decimal("0.04")


async def test_a_call_with_no_price_is_unknown_never_zero(
    database: Database, db_url: str
) -> None:
    await put(db_url, cost=None)
    await put(db_url, cost="0.010000")
    report = await usage_report(database, env={})
    assert report.unknown_cost_calls == 1
    row = report.workflows[0]
    assert row.unknown_cost_calls == 1
    assert row.avg_cost_usd == Decimal("0.010000")


async def test_cache_hits_are_counted_apart_and_save_the_average_cost(
    database: Database, db_url: str
) -> None:
    await put(db_url, cost="0.020000")
    for _ in range(3):
        await put(db_url, cache=True, tokens_in=0, tokens_out=0, cost="0")
    report = await usage_report(database, env={})
    row = report.rows[0]
    assert (row.calls, row.cache_hits) == (1, 3)
    assert row.cache_savings_usd == Decimal("0.060000")
    assert report.cache_savings_usd == Decimal("0.06")


async def test_groups_by_model_and_prompt_version(
    database: Database, db_url: str
) -> None:
    await put(db_url, model="a", version="v1")
    await put(db_url, model="a", version="v2")
    await put(db_url, model="b", version="v1")
    report = await usage_report(database, env={})
    assert [(r.model, r.prompt_version) for r in report.rows] == [
        ("a", "v1"),
        ("a", "v2"),
        ("b", "v1"),
    ]
    assert len(report.workflows) == 1 and report.workflows[0].calls == 3


async def test_only_the_asked_window_counts(database: Database, db_url: str) -> None:
    await put(db_url, when=datetime.now(UTC) - timedelta(days=40))
    await put(db_url)
    assert (await usage_report(database, env={})).workflows[0].calls == 1
    assert (await usage_report(database, days=60, env={})).workflows[0].calls == 2
    assert (await usage_report(database, days=-5, env={})).days == 1
    assert (await usage_report(database, days=9999, env={})).days == 365


async def test_the_paid_estimate_uses_only_a_price_the_founder_set(
    database: Database, db_url: str
) -> None:
    await put(db_url, tokens_in=2_000_000, tokens_out=1_000_000)
    off = await usage_report(database, env={})
    assert off.compare.configured is False and off.compare.estimate_usd is None
    on = await usage_report(
        database,
        env={"AI_COMPARE_PRICE": "3, 15", "AI_COMPARE_LABEL": "Big model"},
    )
    assert on.compare.configured is True
    assert on.compare.label == "Big model"
    assert on.compare.estimate_usd == Decimal("21.00")
    bad = await usage_report(database, env={"AI_COMPARE_PRICE": "three,fifteen"})
    assert bad.compare.configured is False


async def test_the_report_carries_no_text_and_no_user_ids(
    database: Database, db_url: str
) -> None:
    user = uuid.uuid4()
    await put(db_url, user=user)
    text = (await usage_report(database, env={})).model_dump_json()
    assert str(user) not in text
    assert "userId" not in text and "user_id" not in text


@pytest.fixture
async def app(db_url: str) -> AsyncIterator[FastAPI]:
    await upgrade(db_url)
    application = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    yield application
    await application.state.database.dispose()


async def test_the_route_needs_the_web_server_and_returns_camel_case(
    app: FastAPI, db_url: str
) -> None:
    await put(db_url)
    async with http(app) as client:
        refused = await client.get("/internal/admin/ai-usage")
        assert refused.status_code == 401
        r = await client.get("/internal/admin/ai-usage?days=7", headers=auth(USER_A))
    assert r.status_code == 200, r.text
    body = json.loads(r.text)
    assert body["days"] == 7
    assert body["workflows"][0]["workflow"] == "evaluate"
    assert body["goldenSet"] is None
    assert {"totalCostUsd", "cacheSavingsUsd", "compare", "unknownCostCalls"} <= set(
        body
    )


async def test_the_workflow_average_matches_the_row_average_with_rejected_calls(
    database: Database, db_url: str
) -> None:
    await put(db_url, cost="0.010000")
    await put(db_url, cost="0.010000")
    await put(db_url, outcome="rejected", cost="0.010000")
    await put(db_url, outcome="rejected", cost=None)
    report = await usage_report(database, env={})
    assert report.rows[0].avg_cost_usd == Decimal("0.010000")
    assert report.workflows[0].avg_cost_usd == Decimal("0.010000")
    assert report.workflows[0].cost_usd == Decimal("0.030000")
