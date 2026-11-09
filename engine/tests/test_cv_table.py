"""The cv_file table: constraints, uniqueness and index."""

import uuid

import asyncpg
import pytest

from tests.db import fetch, upgrade

INSERT = """
insert into engine.cv_file
  (user_id, storage_key, filename, mime, size_bytes, extracted_text)
values ($1, $2, 'cv.pdf', $3, $4, 'text')
"""


async def run(url: str, query: str, *args: object) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()


async def test_a_valid_row_gets_defaults(db_url: str) -> None:
    await upgrade(db_url)
    await run(db_url, INSERT, uuid.uuid4(), "cv/a", "pdf", 10)
    rows = await fetch(
        db_url, "select id, parse_status, created_at from engine.cv_file"
    )
    assert len(rows) == 1
    assert rows[0]["parse_status"] == "extracted"
    assert rows[0]["id"] is not None
    assert rows[0]["created_at"] is not None


@pytest.mark.parametrize(
    ("mime", "size", "constraint"),
    [("txt", 1, "ck_cv_file_mime"), ("pdf", -1, "ck_cv_file_size")],
)
async def test_check_constraints_reject_bad_rows(
    db_url: str, mime: str, size: int, constraint: str
) -> None:
    await upgrade(db_url)
    with pytest.raises(asyncpg.CheckViolationError, match=constraint):
        await run(db_url, INSERT, uuid.uuid4(), "cv/a", mime, size)


async def test_parse_status_is_limited_to_the_known_values(db_url: str) -> None:
    await upgrade(db_url)
    await run(db_url, INSERT, uuid.uuid4(), "cv/a", "docx", 1)
    for status in ("parsing", "parsed", "failed"):
        await run(db_url, "update engine.cv_file set parse_status = $1", status)
    with pytest.raises(asyncpg.CheckViolationError, match="ck_cv_file_parse_status"):
        await run(db_url, "update engine.cv_file set parse_status = 'done'")


async def test_storage_key_is_unique(db_url: str) -> None:
    await upgrade(db_url)
    await run(db_url, INSERT, uuid.uuid4(), "cv/a", "pdf", 1)
    with pytest.raises(asyncpg.UniqueViolationError):
        await run(db_url, INSERT, uuid.uuid4(), "cv/a", "pdf", 1)


async def test_the_owner_index_exists(db_url: str) -> None:
    await upgrade(db_url)
    rows = await fetch(
        db_url,
        "select indexname from pg_indexes where schemaname = 'engine' "
        "and tablename = 'cv_file'",
    )
    assert "cv_file_user_created_idx" in {r["indexname"] for r in rows}
