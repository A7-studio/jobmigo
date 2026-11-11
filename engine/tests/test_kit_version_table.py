"""The kit_version table: constraints, uniqueness and cascade."""

import json
import uuid

import asyncpg
import pytest

from tests.db import fetch, upgrade

USER = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")

INSERT = """
insert into engine.kit_version
  (user_id, job_id, track_id, profile_id, profile_version, doc_type, version,
   cache_key, content, fact_check)
values ($1, $2, $3, $4, 1, $5, $6, 'c', $7::jsonb, $8::jsonb)
"""


async def run(url: str, query: str, *args: object) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()


async def seed(url: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    job, track, cv, profile = (uuid.uuid4() for _ in range(4))
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
    await run(
        url,
        "insert into engine.cv_file (id, user_id, storage_key, filename, mime, "
        "size_bytes, extracted_text, parse_status) "
        "values ($1, $2, $3, 'cv.pdf', 'pdf', 1, 't', 'parsed')",
        cv,
        USER,
        f"cv/{cv}",
    )
    await run(
        url,
        "insert into engine.profile (id, user_id, source_cv_id) values ($1, $2, $3)",
        profile,
        USER,
        cv,
    )
    return job, track, profile


async def add(
    url: str,
    ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    doc_type: str = "cv",
    version: int = 1,
) -> None:
    job, track, profile = ids
    await run(
        url,
        INSERT,
        USER,
        job,
        track,
        profile,
        doc_type,
        version,
        json.dumps({}),
        json.dumps({}),
    )


async def test_a_valid_row_gets_defaults(db_url: str) -> None:
    await upgrade(db_url)
    ids = await seed(db_url)
    await add(db_url, ids)
    rows = await fetch(
        db_url, "select usage_event_ids, created_at from engine.kit_version"
    )
    assert len(rows) == 1
    assert rows[0]["usage_event_ids"] == "[]"
    assert rows[0]["created_at"] is not None


@pytest.mark.parametrize("doc_type", ["cv", "letter", "proposal", "answers"])
async def test_every_document_type_is_accepted(db_url: str, doc_type: str) -> None:
    await upgrade(db_url)
    ids = await seed(db_url)
    await add(db_url, ids, doc_type)


async def test_an_unknown_document_type_or_version_zero_is_refused(
    db_url: str,
) -> None:
    await upgrade(db_url)
    ids = await seed(db_url)
    with pytest.raises(asyncpg.CheckViolationError, match="ck_kit_version_doc_type"):
        await add(db_url, ids, "poem")
    with pytest.raises(asyncpg.CheckViolationError, match="ck_kit_version_version"):
        await add(db_url, ids, "cv", 0)


async def test_versions_are_unique_per_job_track_and_type(db_url: str) -> None:
    await upgrade(db_url)
    ids = await seed(db_url)
    await add(db_url, ids)
    await add(db_url, ids, "cv", 2)
    await add(db_url, ids, "letter", 1)
    with pytest.raises(asyncpg.UniqueViolationError):
        await add(db_url, ids, "cv", 1)


@pytest.mark.parametrize(("table", "index"), [("job", 0), ("track", 1), ("profile", 2)])
async def test_a_row_follows_its_job_track_and_profile(
    db_url: str, table: str, index: int
) -> None:
    await upgrade(db_url)
    ids = await seed(db_url)
    await add(db_url, ids)
    await run(db_url, f"delete from engine.{table} where id = $1", ids[index])  # noqa: S608
    assert await fetch(db_url, "select 1 from engine.kit_version") == []


async def test_a_row_needs_a_real_job_track_and_profile(db_url: str) -> None:
    await upgrade(db_url)
    fake = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await add(db_url, fake)
