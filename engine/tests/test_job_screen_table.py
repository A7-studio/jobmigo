"""The job_screen table: constraints, uniqueness and cascade."""

import uuid

import asyncpg
import pytest

from tests.db import downgrade, fetch, upgrade

USER = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")

INSERT = """
insert into engine.job_screen
  (user_id, job_id, track_id, variant_version, rules_key, outcome, removed_by)
values ($1, $2, $3, 1, 'k', $4, $5)
"""


async def run(url: str, query: str, *args: object) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()


async def seed(url: str) -> tuple[uuid.UUID, uuid.UUID]:
    job, track = uuid.uuid4(), uuid.uuid4()
    await run(
        url,
        "insert into engine.job (id, user_id, company, title, dedupe_key, description) "
        "values ($1, $2, 'Acme', 'Engineer', $3, 'text')",
        job,
        USER,
        f"acme-{job}",
    )
    await run(
        url,
        "insert into engine.track (id, user_id, name) values ($1, $2, $3)",
        track,
        USER,
        f"Track {track}",
    )
    return job, track


async def test_a_valid_row_gets_defaults(db_url: str) -> None:
    await upgrade(db_url)
    job, track = await seed(db_url)
    await run(db_url, INSERT, USER, job, track, "passed", None)
    rows = await fetch(
        db_url, "select id, outcome, created_at, updated_at from engine.job_screen"
    )
    assert len(rows) == 1
    assert rows[0]["outcome"] == "passed"
    assert rows[0]["id"] is not None
    assert rows[0]["created_at"] is not None


@pytest.mark.parametrize(
    ("outcome", "removed_by", "constraint"),
    [
        ("done", None, "ck_job_screen_outcome"),
        ("removed", "me", "ck_job_screen_removed_by"),
        ("removed", None, "ck_job_screen_removed"),
        ("passed", "gate", "ck_job_screen_removed"),
    ],
)
async def test_check_constraints_reject_bad_rows(
    db_url: str, outcome: str, removed_by: str | None, constraint: str
) -> None:
    await upgrade(db_url)
    job, track = await seed(db_url)
    with pytest.raises(asyncpg.CheckViolationError, match=constraint):
        await run(db_url, INSERT, USER, job, track, outcome, removed_by)


async def test_a_flagged_row_is_valid_and_needs_no_removed_by(db_url: str) -> None:
    await upgrade(db_url)
    job, track = await seed(db_url)
    await run(db_url, INSERT, USER, job, track, "flagged", None)
    rows = await fetch(db_url, "select outcome, removed_by from engine.job_screen")
    assert [(r["outcome"], r["removed_by"]) for r in rows] == [("flagged", None)]


async def test_a_flagged_row_cannot_claim_to_be_removed_by_someone(
    db_url: str,
) -> None:
    await upgrade(db_url)
    job, track = await seed(db_url)
    with pytest.raises(asyncpg.CheckViolationError, match="ck_job_screen_removed"):
        await run(db_url, INSERT, USER, job, track, "flagged", "screen")


async def test_one_row_per_job_and_track(db_url: str) -> None:
    await upgrade(db_url)
    job, track = await seed(db_url)
    await run(db_url, INSERT, USER, job, track, "removed", "gate")
    with pytest.raises(asyncpg.UniqueViolationError):
        await run(db_url, INSERT, USER, job, track, "passed", None)


async def test_rows_follow_their_job_and_track(db_url: str) -> None:
    await upgrade(db_url)
    job, track = await seed(db_url)
    await run(db_url, INSERT, USER, job, track, "passed", None)
    await run(db_url, "delete from engine.job where id = $1", job)
    assert await fetch(db_url, "select 1 from engine.job_screen") == []

    job, track = await seed(db_url)
    await run(db_url, INSERT, USER, job, track, "passed", None)
    await run(db_url, "delete from engine.track where id = $1", track)
    assert await fetch(db_url, "select 1 from engine.job_screen") == []


async def test_a_row_needs_a_real_job_and_track(db_url: str) -> None:
    await upgrade(db_url)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await run(db_url, INSERT, USER, uuid.uuid4(), uuid.uuid4(), "passed", None)


async def test_upgrading_from_0009_keeps_rows_and_downgrading_unflags(
    db_url: str,
) -> None:
    await upgrade(db_url, "0009")
    job, track = await seed(db_url)
    await run(db_url, INSERT, USER, job, track, "removed", "gate")
    with pytest.raises(asyncpg.CheckViolationError, match="ck_job_screen_outcome"):
        other_job, other_track = await seed(db_url)
        await run(db_url, INSERT, USER, other_job, other_track, "flagged", None)
    await upgrade(db_url)
    other_job, other_track = await seed(db_url)
    await run(db_url, INSERT, USER, other_job, other_track, "flagged", None)
    await downgrade(db_url, "0009")
    rows = await fetch(db_url, "select outcome from engine.job_screen order by outcome")
    assert [r["outcome"] for r in rows] == ["passed", "removed"]
