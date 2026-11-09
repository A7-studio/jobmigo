"""Starting, running and reading a parse against the real test database."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest

from engine.ai.errors import AiNotConfiguredError, AiUnavailableError
from engine.cv import parse_service as ps
from engine.cv.service import CvOut
from engine.db import Database
from engine.errors import ApiError
from tests.db import fetch, upgrade
from tests.test_ai_gateway import ENV, Fake, reply
from tests.test_cv_parse import GOOD

USER = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")
OTHER = uuid.UUID("9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d")
TEXT = "Jane Secret-Name, Flutter engineer at Secret-Corp"


@pytest.fixture
async def database(db_url: str) -> AsyncIterator[Database]:
    await upgrade(db_url)
    db = Database(db_url)
    yield db
    await db.dispose()


async def add_cv(url: str, user: uuid.UUID = USER, status: str = "extracted") -> str:
    cv = uuid.uuid4()
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(
            "insert into engine.cv_file "
            "(id, user_id, storage_key, filename, mime, size_bytes, extracted_text, "
            "parse_status) values ($1, $2, $3, 'cv.pdf', 'pdf', 1, $4, $5)",
            cv,
            user,
            f"cv/{cv}",
            TEXT,
            status,
        )
    finally:
        await connection.close()
    return str(cv)


async def state(db: Database, cv: str, user: uuid.UUID = USER) -> CvOut:
    return await ps.get_cv(user_id=user, cv_id=cv, database=db)


def good() -> object:
    return reply(json.dumps(GOOD))


async def run(db: Database, cv: str, provider: Fake, user: uuid.UUID = USER) -> None:
    jobs = ps.ParseJobs(db)
    await ps.start_parse(
        user_id=user, cv_id=cv, database=db, jobs=jobs, env=ENV, provider=provider
    )
    await asyncio.gather(*jobs._tasks)


async def test_success_writes_the_draft_and_sets_parsed(
    database: Database, db_url: str
) -> None:
    cv = await add_cv(db_url)
    await run(database, cv, Fake(good()))  # type: ignore[arg-type]
    out = await state(database, cv)
    assert (out.parse_status, out.parse_error) == ("parsed", None)
    draft = await ps.get_draft(user_id=USER, cv_id=cv, database=database)
    assert draft.headline == "Flutter engineer"
    assert [e.company for e in draft.experiences] == ["Acme"]
    assert [s.name for s in draft.skills] == ["Dart", "Flutter"]
    assert draft.achievements[0].experience_id == draft.experiences[0].id
    statuses = {
        row["status"]
        for table in ("experience", "skill", "achievement", "project", "education")
        for row in await fetch(db_url, f"select status from engine.{table}")  # noqa: S608
    }
    assert statuses == {"extracted"}


@pytest.mark.parametrize(
    ("replies", "code"),
    [
        ([reply("x"), reply("y")], "ai_output_invalid"),
        ([AiUnavailableError()], "ai_unavailable"),
        ([reply(json.dumps({"headline": "only"}))], "no_profile_found"),
        ([RuntimeError("boom")], "internal"),
    ],
)
async def test_each_failure_code_is_stored_and_clears_on_a_retry(
    database: Database, db_url: str, replies: list[object], code: str
) -> None:
    cv = await add_cv(db_url)
    await run(database, cv, Fake(*replies))  # type: ignore[arg-type]
    failed = await state(database, cv)
    assert (failed.parse_status, failed.parse_error) == ("failed", code)
    assert await fetch(db_url, "select * from engine.profile") == []

    await run(database, cv, Fake(good()))  # type: ignore[arg-type]
    done = await state(database, cv)
    assert (done.parse_status, done.parse_error) == ("parsed", None)


async def test_text_too_long_is_a_stored_failure(
    database: Database, db_url: str
) -> None:
    cv = await add_cv(db_url)
    connection = await asyncpg.connect(db_url)
    await connection.execute(
        "update engine.cv_file set extracted_text = repeat('x', 60001)"
    )
    await connection.close()
    provider = Fake()
    await run(database, cv, provider)
    assert (await state(database, cv)).parse_error == "text_too_long"
    assert provider.calls == []


async def test_a_second_start_while_parsing_is_a_no_op(
    database: Database, db_url: str
) -> None:
    cv = await add_cv(db_url)
    release = asyncio.Event()

    class Slow(Fake):
        async def complete(self, request):  # type: ignore[no-untyped-def]
            await release.wait()
            return await super().complete(request)

    provider = Slow(good())  # type: ignore[arg-type]
    jobs = ps.ParseJobs(database)
    first = await ps.start_parse(
        user_id=USER, cv_id=cv, database=database, jobs=jobs, env=ENV, provider=provider
    )
    second = await ps.start_parse(
        user_id=USER, cv_id=cv, database=database, jobs=jobs, env=ENV, provider=provider
    )
    assert first.parse_status == second.parse_status == "parsing"
    assert len(jobs._tasks) == 1
    release.set()
    await asyncio.gather(*jobs._tasks)
    assert len(provider.calls) == 1


async def test_a_parsed_cv_is_not_run_again(database: Database, db_url: str) -> None:
    cv = await add_cv(db_url)
    await run(database, cv, Fake(good()))  # type: ignore[arg-type]
    provider = Fake()
    await run(database, cv, provider)
    assert provider.calls == []
    assert (await state(database, cv)).parse_status == "parsed"


async def test_another_users_cv_looks_like_a_missing_one(
    database: Database, db_url: str
) -> None:
    cv = await add_cv(db_url)
    for call in (
        ps.get_cv(user_id=OTHER, cv_id=cv, database=database),
        ps.get_draft(user_id=OTHER, cv_id=cv, database=database),
        ps.start_parse(
            user_id=OTHER,
            cv_id=cv,
            database=database,
            jobs=ps.ParseJobs(database),
            env=ENV,
            provider=Fake(),
        ),
        ps.get_cv(user_id=USER, cv_id="not-a-uuid", database=database),
    ):
        with pytest.raises(ApiError) as caught:
            await call
        assert (caught.value.status, caught.value.code) == (404, "not_found")
    assert (await state(database, cv)).parse_status == "extracted"


async def test_the_draft_is_not_readable_before_it_exists(
    database: Database, db_url: str
) -> None:
    cv = await add_cv(db_url)
    with pytest.raises(ApiError) as caught:
        await ps.get_draft(user_id=USER, cv_id=cv, database=database)
    assert caught.value.status == 404


async def test_deleting_the_cv_during_the_parse_leaves_no_rows(
    database: Database, db_url: str
) -> None:
    cv = await add_cv(db_url)
    started, release = asyncio.Event(), asyncio.Event()

    class Slow(Fake):
        async def complete(self, request):  # type: ignore[no-untyped-def]
            started.set()
            await release.wait()
            return await super().complete(request)

    jobs = ps.ParseJobs(database)
    await ps.start_parse(
        user_id=USER,
        cv_id=cv,
        database=database,
        jobs=jobs,
        env=ENV,
        provider=Slow(good()),  # type: ignore[arg-type]
    )
    await started.wait()
    connection = await asyncpg.connect(db_url)
    await connection.execute("delete from engine.cv_file")
    await connection.close()
    release.set()
    await asyncio.gather(*jobs._tasks)
    assert await fetch(db_url, "select * from engine.profile") == []
    assert await fetch(db_url, "select * from engine.experience") == []


async def test_the_sweep_fails_only_stale_parsing_rows(
    database: Database, db_url: str
) -> None:
    stale = await add_cv(db_url, status="parsing")
    fresh = await add_cv(db_url, status="parsed")
    waiting = await add_cv(db_url)
    assert await ps.sweep_interrupted(database) == 1
    out = await state(database, stale)
    assert (out.parse_status, out.parse_error) == ("failed", "interrupted")
    assert (await state(database, fresh)).parse_status == "parsed"
    assert (await state(database, waiting)).parse_status == "extracted"
    # and the interrupted CV can be retried
    await run(database, stale, Fake(good()))  # type: ignore[arg-type]
    assert (await state(database, stale)).parse_status == "parsed"


async def test_shutdown_cancels_a_running_parse_and_leaves_it_to_the_sweep(
    database: Database, db_url: str
) -> None:
    cv = await add_cv(db_url)
    started = asyncio.Event()

    class Hang(Fake):
        async def complete(self, request):  # type: ignore[no-untyped-def]
            started.set()
            await asyncio.sleep(60)
            return await super().complete(request)

    jobs = ps.ParseJobs(database)
    await ps.start_parse(
        user_id=USER,
        cv_id=cv,
        database=database,
        jobs=jobs,
        env=ENV,
        provider=Hang(),
    )
    await started.wait()
    await jobs.shutdown()
    assert (await state(database, cv)).parse_status == "parsing"
    await ps.sweep_interrupted(database)
    assert (await state(database, cv)).parse_error == "interrupted"


async def test_a_missing_ai_setting_fails_before_any_claim(
    database: Database, db_url: str
) -> None:
    cv = await add_cv(db_url)
    with pytest.raises(AiNotConfiguredError):
        await ps.start_parse(
            user_id=USER,
            cv_id=cv,
            database=database,
            jobs=ps.ParseJobs(database),
            env={},
        )
    assert (await state(database, cv)).parse_status == "extracted"


async def test_nothing_sensitive_is_logged(
    database: Database, db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    ok = await add_cv(db_url)
    bad = await add_cv(db_url)
    await run(database, ok, Fake(good()))  # type: ignore[arg-type]
    await run(database, bad, Fake(RuntimeError("Secret-Corp leaked")))
    logged = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert "cv parse failed" in logged
    for secret in ("Secret-Name", "Secret-Corp", "Acme", "Flutter engineer"):
        assert secret not in logged
