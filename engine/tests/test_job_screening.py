"""Screening a saved job against every track, against the real test database."""

import json
import logging
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest

from engine.ai.errors import AiUnavailableError
from engine.ai.provider import AiRequest, AiResponse
from engine.db import Database
from engine.errors import ApiError
from engine.jobs.screening import list_screens, screen_job
from tests.db import fetch, upgrade
from tests.test_ai_gateway import ENV, Fake

USER = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")
OTHER = uuid.UUID("9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d")
POSTING = "Our product helps people trade crypto tokens on mobile. Remote friendly."


@pytest.fixture
async def database(db_url: str) -> AsyncIterator[Database]:
    await upgrade(db_url)
    db = Database(db_url)
    yield db
    await db.dispose()


class Smart:
    """A provider that answers by reading the request, and counts its calls."""

    name = "smart"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: AiRequest) -> AiResponse:
        self.calls += 1
        hit = "Dealbreakers: no crypto" in request.user
        hits = (
            [{"dealbreaker": "no crypto", "quote": "trade crypto tokens"}]
            if hit
            else []
        )
        body = {"dealbreaker_hits": hits, "role_match": "yes", "note": "Close."}
        return AiResponse(json.dumps(body), 10, 5)


async def run(url: str, query: str, *args: object) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()


async def add_job(
    url: str, user: uuid.UUID = USER, company: str = "Acme", text: str = POSTING
) -> str:
    job = uuid.uuid4()
    await run(
        url,
        "insert into engine.job (id, user_id, company, title, dedupe_key, description) "
        "values ($1, $2, $3, 'Flutter Engineer', $4, $5)",
        job,
        user,
        company,
        f"k-{job}",
        text,
    )
    return str(job)


async def add_track(
    url: str,
    name: str,
    user: uuid.UUID = USER,
    dealbreakers: list[str] | None = None,
    do_not_apply: list[str] | None = None,
) -> str:
    track = uuid.uuid4()
    await run(
        url,
        "insert into engine.track (id, user_id, name, dealbreakers, do_not_apply) "
        "values ($1, $2, $3, $4::jsonb, $5)",
        track,
        user,
        name,
        json.dumps(dealbreakers or []),
        do_not_apply or [],
    )
    return str(track)


async def test_two_tracks_can_reach_different_outcomes(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url)
    strict = await add_track(db_url, "Strict", dealbreakers=["no crypto"])
    easy = await add_track(db_url, "Easy")
    provider = Smart()
    results = await screen_job(
        user_id=USER, job_id=job, database=database, env=ENV, provider=provider
    )
    by_track = {str(r.track_id): r for r in results}
    assert by_track[strict].outcome == "removed"
    assert by_track[strict].removed_by == "screen"
    assert by_track[strict].reason_code == "dealbreaker"
    assert "trade crypto tokens" in (by_track[strict].reason or "")
    assert by_track[easy].outcome == "passed"
    easy_screen = by_track[easy].screen
    assert easy_screen is not None
    assert easy_screen.role_match == "yes"
    assert provider.calls == 2
    assert not by_track[strict].stale


async def test_a_gate_removal_makes_no_model_call(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url, company="Acme")
    gated = await add_track(db_url, "Gated", do_not_apply=["Acme"])
    provider = Smart()
    results = await screen_job(
        user_id=USER, job_id=job, database=database, env=ENV, provider=provider
    )
    assert [str(r.track_id) for r in results] == [gated]
    assert results[0].outcome == "removed"
    assert results[0].removed_by == "gate"
    assert results[0].reason_code == "do_not_apply"
    assert provider.calls == 0
    assert await fetch(db_url, "select 1 from engine.usage_event") == []


async def test_an_unconfigured_model_leaves_the_job_unscreened(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url)
    await add_track(db_url, "Open")
    gated = await add_track(db_url, "Gated", do_not_apply=["Acme"])
    results = await screen_job(
        user_id=USER, job_id=job, database=database, env={}, provider=Smart()
    )
    by_track = {str(r.track_id): r for r in results}
    assert by_track[gated].outcome == "removed"  # the gate result is still saved
    unscreened = next(r for r in results if str(r.track_id) != gated)
    assert unscreened.outcome == "unscreened"
    assert unscreened.reason_code == "ai_not_configured"
    assert unscreened.removed_by is None


async def test_an_unavailable_model_leaves_the_job_unscreened(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url)
    await add_track(db_url, "Open")
    results = await screen_job(
        user_id=USER,
        job_id=job,
        database=database,
        env=ENV,
        provider=Fake(AiUnavailableError()),
    )
    assert results[0].outcome == "unscreened"
    assert results[0].reason_code == "ai_unavailable"


async def test_a_second_run_reuses_the_cache_and_writes_no_second_row(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url)
    await add_track(db_url, "One", dealbreakers=["no crypto"])
    await add_track(db_url, "Two")
    provider = Smart()
    first = await screen_job(
        user_id=USER, job_id=job, database=database, env=ENV, provider=provider
    )
    second = await screen_job(
        user_id=USER, job_id=job, database=database, env=ENV, provider=provider
    )
    assert provider.calls == 2
    assert [r.outcome for r in second] == [r.outcome for r in first]
    assert len(await fetch(db_url, "select 1 from engine.job_screen")) == 2


async def test_a_rule_edit_makes_the_result_stale_without_a_version_bump(
    db_url: str, database: Database
) -> None:
    # Editing preferences does not move `variant_version`, so staleness must not
    # depend on it. These are the same kind of edits `patch_preferences` makes.
    job = await add_job(db_url)
    track = await add_track(db_url, "One")
    await screen_job(
        user_id=USER, job_id=job, database=database, env=ENV, provider=Smart()
    )
    before = await list_screens(user_id=USER, job_id=job, database=database)
    assert not before[0].stale
    edits = (
        (
            "dealbreakers",
            "update engine.track set dealbreakers = '[\"no gambling\"]' where id = $1",
        ),
        (
            "work_modes",
            "update engine.track set work_modes = array['remote'] where id = $1",
        ),
        (
            "do_not_apply",
            "update engine.track set do_not_apply = array['Other'] where id = $1",
        ),
    )
    for column, statement in edits:
        await run(db_url, statement, uuid.UUID(track))
        after = await list_screens(user_id=USER, job_id=job, database=database)
        assert after[0].stale, column
        assert after[0].variant_version == 1


async def test_a_change_that_no_screen_reads_leaves_the_result_current(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url)
    track = await add_track(db_url, "One")
    await screen_job(
        user_id=USER, job_id=job, database=database, env=ENV, provider=Smart()
    )
    await run(
        db_url,
        "update engine.track set variant_version = variant_version + 1, "
        "salary_floor = 1000 where id = $1",
        uuid.UUID(track),
    )
    after = await list_screens(user_id=USER, job_id=job, database=database)
    assert not after[0].stale


async def test_a_failed_rerun_does_not_erase_an_earlier_result(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url)
    track = await add_track(db_url, "One")
    await screen_job(
        user_id=USER, job_id=job, database=database, env=ENV, provider=Smart()
    )
    await run(
        db_url,
        "update engine.track set dealbreakers = '[\"no gambling\"]'::jsonb, "
        "variant_version = 2 where id = $1",
        uuid.UUID(track),
    )
    results = await screen_job(
        user_id=USER,
        job_id=job,
        database=database,
        env=ENV,
        provider=Fake(AiUnavailableError()),
    )
    assert results[0].outcome == "passed"
    assert results[0].variant_version == 1
    assert results[0].stale


async def test_another_users_job_and_tracks_are_never_touched(
    db_url: str, database: Database
) -> None:
    theirs = await add_job(db_url, user=OTHER)
    mine = await add_job(db_url, user=USER)
    await add_track(db_url, "Mine", user=USER)
    await add_track(db_url, "Theirs", user=OTHER)
    with pytest.raises(ApiError) as error:
        await screen_job(
            user_id=USER, job_id=theirs, database=database, env=ENV, provider=Smart()
        )
    assert error.value.code == "not_found"
    with pytest.raises(ApiError) as error:
        await list_screens(user_id=USER, job_id=theirs, database=database)
    assert error.value.code == "not_found"
    results = await screen_job(
        user_id=USER, job_id=mine, database=database, env=ENV, provider=Smart()
    )
    assert [r.track_name for r in results] == ["Mine"]
    rows = await fetch(db_url, "select user_id from engine.job_screen")
    assert {row["user_id"] for row in rows} == {USER}


async def test_a_job_with_no_tracks_asks_for_a_track(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url)
    with pytest.raises(ApiError) as error:
        await screen_job(
            user_id=USER, job_id=job, database=database, env=ENV, provider=Smart()
        )
    assert error.value.status == 409
    assert error.value.code == "no_tracks"


async def test_a_bad_job_id_is_not_found(database: Database) -> None:
    with pytest.raises(ApiError) as error:
        await list_screens(user_id=USER, job_id="nope", database=database)
    assert error.value.code == "not_found"


async def test_a_deleted_track_does_not_fail_the_other_results(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url)
    gone = await add_track(db_url, "Gone")
    kept = await add_track(db_url, "Kept")

    class DeletesOne(Smart):
        async def complete(self, request: AiRequest) -> AiResponse:
            await run(db_url, "delete from engine.track where id = $1", uuid.UUID(gone))
            return await super().complete(request)

    results = await screen_job(
        user_id=USER, job_id=job, database=database, env=ENV, provider=DeletesOne()
    )
    assert [str(r.track_id) for r in results] == [kept]


async def test_one_unexpected_failure_still_saves_the_other_results(
    db_url: str, database: Database
) -> None:
    job = await add_job(db_url)
    await add_track(db_url, "A", do_not_apply=["Acme"])
    await add_track(db_url, "B")

    class Breaks:
        name = "breaks"

        async def complete(self, request: AiRequest) -> AiResponse:
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await screen_job(
            user_id=USER, job_id=job, database=database, env=ENV, provider=Breaks()
        )
    saved = await list_screens(user_id=USER, job_id=job, database=database)
    assert [(r.track_name, r.outcome) for r in saved] == [("A", "removed")]


async def test_no_posting_text_is_logged_when_the_screen_fails(
    db_url: str, database: Database, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    job = await add_job(db_url)
    await add_track(db_url, "One", dealbreakers=["no crypto"])
    await screen_job(
        user_id=USER,
        job_id=job,
        database=database,
        env=ENV,
        provider=Fake(AiUnavailableError()),
    )
    assert "crypto" not in caplog.text


async def test_no_posting_text_is_logged(
    db_url: str, database: Database, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    job = await add_job(db_url)
    await add_track(db_url, "One", dealbreakers=["no crypto"])
    await screen_job(
        user_id=USER, job_id=job, database=database, env=ENV, provider=Smart()
    )
    assert "crypto" not in caplog.text
