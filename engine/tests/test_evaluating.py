"""Evaluating a saved job for a track, against the real test database."""

import json
import logging
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest

from engine.ai.errors import AiNotConfiguredError, AiUnavailableError
from engine.ai.provider import AiRequest, AiResponse
from engine.db import Database
from engine.errors import ApiError
from engine.jobs.evaluating import evaluate_job, list_evaluations
from tests.db import fetch, upgrade
from tests.profile_seed import Seeded, seed_profile
from tests.test_ai_gateway import ENV as CHEAP_ENV

ENV = {**CHEAP_ENV, "AI_STRONG_MODEL": "deepseek/model-b", "AI_STRONG_PRICE": "3,6"}
USER = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")
OTHER = uuid.UUID("9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d")
POSTING = (
    "Requirements\n- Flutter experience\n- Rust experience\n"
    "We pay USD 3,000 to 4,500 per month."
)


@pytest.fixture
async def database(db_url: str) -> AsyncIterator[Database]:
    await upgrade(db_url)
    db = Database(db_url)
    yield db
    await db.dispose()


class Smart:
    """Answers both evaluation tasks by reading the request, and counts its calls."""

    name = "smart"

    def __init__(self) -> None:
        self.extract_calls = 0
        self.evidence_calls = 0
        self.requests: list[AiRequest] = []

    async def complete(self, request: AiRequest) -> AiResponse:
        self.requests.append(request)
        if "list what it asks" in request.system:
            self.extract_calls += 1
            return AiResponse(json.dumps(self.extraction(request)), 10, 5)
        self.evidence_calls += 1
        return AiResponse(json.dumps(self.evidence(request)), 20, 8)

    def extraction(self, request: AiRequest) -> dict[str, object]:
        if "Flutter experience" not in request.user:
            return {"requirements": [], "pay": None}
        return {
            "requirements": [
                {
                    "need": "Flutter experience",
                    "importance": "must",
                    "quote": "Flutter experience",
                    "marker": "Requirements",
                },
                {
                    "need": "Rust experience",
                    "importance": "must",
                    "quote": "Rust experience",
                    "marker": "Requirements",
                },
            ],
            "pay": {
                "min": 3000,
                "max": 4500,
                "currency": "USD",
                "period": "month",
                "quote": "USD 3,000 to 4,500 per month",
            },
        }

    def evidence(self, request: AiRequest) -> dict[str, object]:
        return {
            "judgements": [
                {"index": 1, "status": "met", "evidence": ["S1"], "note": "Listed."},
                {"index": 2, "status": "gap", "evidence": [], "note": "Not shown."},
            ]
        }

    @property
    def calls(self) -> int:
        return self.extract_calls + self.evidence_calls


async def run(url: str, query: str, *args: object) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()


async def add_job(
    url: str, user: uuid.UUID = USER, text: str = POSTING, company: str = "Acme"
) -> str:
    job = uuid.uuid4()
    await run(
        url,
        "insert into engine.job (id, user_id, company, title, location, dedupe_key, "
        "description) values ($1, $2, $3, 'Flutter Engineer', 'Remote', $4, $5)",
        job,
        user,
        company,
        f"k-{job}",
        text,
    )
    return str(job)


async def add_track(url: str, user: uuid.UUID = USER, name: str = "Mobile") -> str:
    track = uuid.uuid4()
    await run(
        url,
        "insert into engine.track (id, user_id, name, salary_floor, currency, "
        "work_modes) values ($1, $2, $3, 1000, 'USD', array['remote'])",
        track,
        user,
        name,
    )
    return str(track)


async def confirmed_profile(url: str, user: uuid.UUID = USER) -> Seeded:
    seeded = await seed_profile(url, user)
    await run(
        url,
        "update engine.skill set status = 'confirmed' where id = $1",
        seeded.skill_ids[0],
    )
    return seeded


def body(track: str) -> dict[str, object]:
    return {"trackId": track}


async def test_a_full_evaluation_is_checked_decided_and_saved(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    provider = Smart()
    result = await evaluate_job(
        user_id=USER,
        job_id=job,
        body=body(track),
        database=database,
        env=ENV,
        provider=provider,
    )
    assert (provider.extract_calls, provider.evidence_calls) == (1, 1)
    assert result.band == "stretch"  # one must-have is a gap
    assert result.summary == "Evidence for 1 of 2 must-haves"
    assert result.main_gap is not None
    assert result.main_gap.need == "Rust experience"
    assert result.stale is False
    flutter, rust = result.requirements
    assert (flutter.status, flutter.importance, flutter.importance_source) == (
        "met",
        "must",
        "posting",
    )
    assert flutter.evidence[0].text == "Flutter"
    assert flutter.evidence[0].kind == "skill"
    assert (rust.status, rust.evidence) == ("gap", [])
    assert result.checks["salary"]["status"] == "meets"
    assert result.checks["salary"]["postingMonthly"] == 4500
    assert result.checks["workMode"] == {"status": "matches", "posting": "remote"}
    rows = await fetch(db_url, "select usage_event_ids from engine.evaluation")
    assert len(rows) == 1
    assert len(json.loads(str(rows[0]["usage_event_ids"]))) == 2


async def test_only_confirmed_facts_reach_the_model_and_the_output(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    provider = Smart()
    await evaluate_job(
        user_id=USER,
        job_id=job,
        body=body(track),
        database=database,
        env=ENV,
        provider=provider,
    )
    sent = next(r.user for r in provider.requests if "<facts>" in r.user)
    assert "S1: Flutter" in sent
    assert "Dart" not in sent  # an extracted skill
    assert "Northwind" not in sent  # an extracted experience


async def test_a_second_identical_evaluation_makes_no_model_call(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    provider = Smart()
    args = {"user_id": USER, "job_id": job, "body": body(track), "database": database}
    first = await evaluate_job(**args, env=ENV, provider=provider)  # type: ignore[arg-type]
    second = await evaluate_job(**args, env=ENV, provider=provider)  # type: ignore[arg-type]
    assert provider.calls == 2
    assert second.id == first.id
    assert len(await fetch(db_url, "select 1 from engine.evaluation")) == 1


async def test_a_changed_profile_runs_again_and_replaces_the_row(
    db_url: str, database: Database
) -> None:
    seeded = await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    provider = Smart()
    args = {"user_id": USER, "job_id": job, "body": body(track), "database": database}
    await evaluate_job(**args, env=ENV, provider=provider)  # type: ignore[arg-type]
    # A second confirmed fact and a new profile version: the model's facts change.
    await run(
        db_url,
        "update engine.skill set status = 'confirmed' where id = $1",
        seeded.skill_ids[1],
    )
    await run(
        db_url,
        "update engine.profile set version = version + 1 where id = $1",
        seeded.profile_id,
    )
    again = await evaluate_job(**args, env=ENV, provider=provider)  # type: ignore[arg-type]
    # The requirements are the same, so the gateway cache answers the extraction.
    assert (provider.extract_calls, provider.evidence_calls) == (1, 2)
    assert again.profile_version == 2
    assert not again.stale
    assert len(await fetch(db_url, "select 1 from engine.evaluation")) == 1


async def test_a_version_change_with_the_same_facts_is_recomputed_from_the_cache(
    db_url: str, database: Database
) -> None:
    seeded = await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    provider = Smart()
    args = {"user_id": USER, "job_id": job, "body": body(track), "database": database}
    await evaluate_job(**args, env=ENV, provider=provider)  # type: ignore[arg-type]
    await run(
        db_url,
        "update engine.profile set version = version + 1 where id = $1",
        seeded.profile_id,
    )
    again = await evaluate_job(**args, env=ENV, provider=provider)  # type: ignore[arg-type]
    assert provider.calls == 2  # both model answers came from the gateway cache
    assert again.profile_version == 2
    assert not again.stale


async def test_a_changed_track_rule_is_recomputed_and_no_longer_stale(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    provider = Smart()
    args = {"user_id": USER, "job_id": job, "body": body(track), "database": database}
    first = await evaluate_job(**args, env=ENV, provider=provider)  # type: ignore[arg-type]
    await run(
        db_url,
        "update engine.track set eligibility = 'Kenya resident' where id = $1",
        uuid.UUID(track),
    )
    stale = await list_evaluations(user_id=USER, job_id=job, database=database)
    assert stale[0].stale
    again = await evaluate_job(**args, env=ENV, provider=provider)  # type: ignore[arg-type]
    assert again.id == first.id
    assert not again.stale
    assert len(await fetch(db_url, "select 1 from engine.evaluation")) == 1


async def test_a_result_is_stale_after_a_profile_or_rule_edit(
    db_url: str, database: Database
) -> None:
    seeded = await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    await evaluate_job(
        user_id=USER,
        job_id=job,
        body=body(track),
        database=database,
        env=ENV,
        provider=Smart(),
    )
    fresh = await list_evaluations(user_id=USER, job_id=job, database=database)
    assert [e.stale for e in fresh] == [False]
    await run(
        db_url,
        "update engine.profile set version = version + 1 where id = $1",
        seeded.profile_id,
    )
    assert (await list_evaluations(user_id=USER, job_id=job, database=database))[
        0
    ].stale
    await run(
        db_url,
        "update engine.profile set version = version - 1 where id = $1",
        seeded.profile_id,
    )
    await run(
        db_url,
        "update engine.track set locations = array['Lagos'] where id = $1",
        uuid.UUID(track),
    )
    assert (await list_evaluations(user_id=USER, job_id=job, database=database))[
        0
    ].stale


async def test_no_confirmed_facts_asks_for_confirmation_before_any_call(
    db_url: str, database: Database
) -> None:
    await seed_profile(db_url, USER)  # every fact is still `extracted`
    job = await add_job(db_url)
    track = await add_track(db_url)
    provider = Smart()
    with pytest.raises(ApiError) as error:
        await evaluate_job(
            user_id=USER,
            job_id=job,
            body=body(track),
            database=database,
            env=ENV,
            provider=provider,
        )
    assert (error.value.status, error.value.code) == (409, "no_confirmed_profile")
    assert provider.calls == 0


async def test_no_profile_at_all_is_the_same_answer(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url)
    track = await add_track(db_url)
    with pytest.raises(ApiError) as error:
        await evaluate_job(
            user_id=USER,
            job_id=job,
            body=body(track),
            database=database,
            env=ENV,
            provider=Smart(),
        )
    assert error.value.code == "no_confirmed_profile"


async def test_a_posting_with_no_requirements_saves_nothing(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url, text="A calm bank job with nothing listed.")
    track = await add_track(db_url)
    provider = Smart()
    with pytest.raises(ApiError) as error:
        await evaluate_job(
            user_id=USER,
            job_id=job,
            body=body(track),
            database=database,
            env=ENV,
            provider=provider,
        )
    assert (error.value.status, error.value.code) == (422, "no_requirements")
    assert provider.evidence_calls == 0
    assert await fetch(db_url, "select 1 from engine.evaluation") == []


async def test_a_failing_model_keeps_the_earlier_result(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    args = {"user_id": USER, "job_id": job, "body": body(track), "database": database}
    first = await evaluate_job(**args, env=ENV, provider=Smart())  # type: ignore[arg-type]
    seeded = await fetch(db_url, "select id from engine.skill order by position")
    await run(
        db_url,
        "update engine.skill set status = 'confirmed' where id = $1",
        seeded[1]["id"],
    )
    await run(db_url, "update engine.profile set version = version + 1")

    class Down:
        name = "down"

        async def complete(self, request: AiRequest) -> AiResponse:
            raise AiUnavailableError()

    with pytest.raises(AiUnavailableError):
        await evaluate_job(**args, env=ENV, provider=Down())  # type: ignore[arg-type]
    kept = await list_evaluations(user_id=USER, job_id=job, database=database)
    assert [e.id for e in kept] == [first.id]
    assert kept[0].profile_version == 1
    assert kept[0].stale  # the profile changed; the old result is still there


async def test_an_unconfigured_model_saves_nothing(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    with pytest.raises(AiNotConfiguredError):
        await evaluate_job(
            user_id=USER,
            job_id=job,
            body=body(track),
            database=database,
            env={},
            provider=Smart(),
        )
    assert await fetch(db_url, "select 1 from engine.evaluation") == []


async def test_another_users_job_track_and_profile_are_never_used(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url, OTHER)  # only the other user has a profile
    theirs = await add_job(db_url, user=OTHER)
    their_track = await add_track(db_url, user=OTHER, name="Theirs")
    mine = await add_job(db_url, user=USER, company="Mine")
    my_track = await add_track(db_url, user=USER, name="Mine")
    cases = (
        (theirs, my_track),
        (mine, their_track),
        (str(uuid.uuid4()), my_track),
        ("nope", my_track),
    )
    for job, track in cases:
        with pytest.raises(ApiError) as error:
            await evaluate_job(
                user_id=USER,
                job_id=job,
                body=body(track),
                database=database,
                env=ENV,
                provider=Smart(),
            )
        assert error.value.code == "not_found", (job, track)
    # My own job and track still cannot borrow the other user's profile.
    with pytest.raises(ApiError) as error:
        await evaluate_job(
            user_id=USER,
            job_id=mine,
            body=body(my_track),
            database=database,
            env=ENV,
            provider=Smart(),
        )
    assert error.value.code == "no_confirmed_profile"
    assert await fetch(db_url, "select 1 from engine.evaluation") == []
    with pytest.raises(ApiError):
        await list_evaluations(user_id=USER, job_id=theirs, database=database)


@pytest.mark.parametrize(
    "bad", [{}, {"trackId": "nope"}, {"trackId": 5}, {"trackId": None}, {"x": 1}]
)
async def test_a_missing_or_malformed_track_id_is_refused(
    db_url: str, database: Database, bad: dict[str, object]
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    with pytest.raises(ApiError) as error:
        await evaluate_job(
            user_id=USER,
            job_id=job,
            body=bad,
            database=database,
            env=ENV,
            provider=Smart(),
        )
    assert (error.value.status, error.value.code) == (422, "validation_failed")


async def test_a_job_deleted_mid_run_is_not_found(
    db_url: str, database: Database
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)

    class DeletesTheJob(Smart):
        async def complete(self, request: AiRequest) -> AiResponse:
            if "compare the requirements" in request.system:
                await run(
                    db_url, "delete from engine.job where id = $1", uuid.UUID(job)
                )
            return await super().complete(request)

    with pytest.raises(ApiError) as error:
        await evaluate_job(
            user_id=USER,
            job_id=job,
            body=body(track),
            database=database,
            env=ENV,
            provider=DeletesTheJob(),
        )
    assert error.value.code == "not_found"


async def test_no_posting_fact_or_quote_text_is_logged(
    db_url: str, database: Database, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    await evaluate_job(
        user_id=USER,
        job_id=job,
        body=body(track),
        database=database,
        env=ENV,
        provider=Smart(),
    )
    for word in ("Flutter experience", "Rust", "Not shown", "Listed."):
        assert word not in caplog.text


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("update engine.track set salary_floor = 5000 where id = $1", "below"),
        ("update engine.track set currency = 'EUR' where id = $1", "unknown"),
    ],
)
async def test_an_edit_to_the_salary_floor_or_currency_is_not_served_from_the_old_row(
    db_url: str, database: Database, statement: str, expected: str
) -> None:
    await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    provider = Smart()
    args = {"user_id": USER, "job_id": job, "body": body(track), "database": database}
    first = await evaluate_job(**args, env=ENV, provider=provider)  # type: ignore[arg-type]
    assert first.checks["salary"]["status"] == "meets"
    await run(db_url, statement, uuid.UUID(track))
    stale = await list_evaluations(user_id=USER, job_id=job, database=database)
    assert stale[0].stale
    again = await evaluate_job(**args, env=ENV, provider=provider)  # type: ignore[arg-type]
    assert not again.stale
    assert again.checks["salary"]["status"] == expected
    assert provider.calls == 2  # the model's answers did not depend on the floor


async def test_another_users_row_at_the_same_key_is_never_read_or_replaced(
    db_url: str, database: Database
) -> None:
    seeded = await confirmed_profile(db_url)
    job = await add_job(db_url)
    track = await add_track(db_url)
    # A row owned by someone else that happens to sit on this job and track.
    await run(
        db_url,
        "insert into engine.evaluation (user_id, job_id, track_id, profile_id, "
        "profile_version, rules_key, cache_key, band, summary, requirements, checks) "
        "values ($1, $2, $3, $4, 1, 'r', 'c', 'poor', 'theirs', '[]'::jsonb, "
        "'{}'::jsonb)",
        OTHER,
        uuid.UUID(job),
        uuid.UUID(track),
        seeded.profile_id,
    )
    provider = Smart()
    with pytest.raises(ApiError) as error:
        await evaluate_job(
            user_id=USER,
            job_id=job,
            body=body(track),
            database=database,
            env=ENV,
            provider=provider,
        )
    assert error.value.code == "not_found"
    rows = await fetch(db_url, "select user_id, band, summary from engine.evaluation")
    assert [(r["user_id"], r["band"], r["summary"]) for r in rows] == [
        (OTHER, "poor", "theirs")
    ]
    assert await list_evaluations(user_id=USER, job_id=job, database=database) == []
