"""The profile draft tables: cascade, scoping columns and constraints."""

import uuid

import asyncpg
import pytest

from tests.db import downgrade, fetch, upgrade

USER = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")
CV = "insert into engine.cv_file (id, user_id, storage_key, filename, mime, size_bytes, extracted_text) values ($1, $2, $3, 'cv.pdf', 'pdf', 1, 't')"  # noqa: E501


async def run(url: str, query: str, *args: object) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()


async def seed_draft(url: str) -> uuid.UUID:
    cv, profile, experience = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await run(url, CV, cv, USER, f"cv/{cv}")
    await run(
        url,
        "insert into engine.profile (id, user_id, source_cv_id, headline) "
        "values ($1, $2, $3, 'h')",
        profile,
        USER,
        cv,
    )
    await run(
        url,
        "insert into engine.experience "
        "(id, user_id, profile_id, position, company, role) "
        "values ($1, $2, $3, 0, 'Acme', 'Engineer')",
        experience,
        USER,
        profile,
    )
    for statement in (
        "insert into engine.skill (user_id, profile_id, position, name) "
        "values ($1, $2, 0, 'Dart')",
        "insert into engine.project (user_id, profile_id, position, name) "
        "values ($1, $2, 0, 'App')",
        "insert into engine.education (user_id, profile_id, position, institution) "
        "values ($1, $2, 0, 'Uni')",
    ):
        await run(url, statement, USER, profile)
    await run(
        url,
        "insert into engine.achievement "
        "(user_id, profile_id, position, text, experience_id) "
        "values ($1, $2, 0, 'Shipped', $3)",
        USER,
        profile,
        experience,
    )
    return cv


TABLES = ("profile", "experience", "skill", "achievement", "project", "education")


async def counts(url: str) -> list[int]:
    rows = await fetch(
        url,
        "select (select count(*) from engine.profile) as a, "
        "(select count(*) from engine.experience) as b, "
        "(select count(*) from engine.skill) as c, "
        "(select count(*) from engine.achievement) as d, "
        "(select count(*) from engine.project) as e, "
        "(select count(*) from engine.education) as f",
    )
    return [int(str(v)) for v in rows[0].values()]


async def test_deleting_the_cv_removes_the_draft_and_every_child(db_url: str) -> None:
    await upgrade(db_url)
    cv = await seed_draft(db_url)
    assert await counts(db_url) == [1] * len(TABLES)
    await run(db_url, "delete from engine.cv_file where id = $1", cv)
    assert await counts(db_url) == [0] * len(TABLES)


async def test_children_default_to_extracted_and_reject_other_values(
    db_url: str,
) -> None:
    await upgrade(db_url)
    await seed_draft(db_url)
    rows = await fetch(db_url, "select status from engine.skill")
    assert rows[0]["status"] == "extracted"
    with pytest.raises(asyncpg.CheckViolationError):
        await run(db_url, "update engine.skill set status = 'bogus'")


async def test_one_draft_per_cv(db_url: str) -> None:
    await upgrade(db_url)
    cv = await seed_draft(db_url)
    with pytest.raises(asyncpg.UniqueViolationError):
        await run(
            db_url,
            "insert into engine.profile (user_id, source_cv_id) values ($1, $2)",
            USER,
            cv,
        )


async def test_parse_error_only_on_a_failed_row_and_only_known_codes(
    db_url: str,
) -> None:
    await upgrade(db_url)
    cv = uuid.uuid4()
    await run(db_url, CV, cv, USER, "cv/x")
    with pytest.raises(asyncpg.CheckViolationError):
        await run(
            db_url,
            "update engine.cv_file set parse_error = 'internal' where id = $1",
            cv,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await run(
            db_url,
            "update engine.cv_file set parse_status = 'failed', "
            "parse_error = 'made_up' where id = $1",
            cv,
        )
    await run(
        db_url,
        "update engine.cv_file set parse_status = 'failed', "
        "parse_error = 'internal' where id = $1",
        cv,
    )


async def test_downgrade_removes_the_draft_tables_and_the_column(db_url: str) -> None:
    await upgrade(db_url)
    await downgrade(db_url)
    tables = await fetch(
        db_url,
        "select table_name from information_schema.tables "
        "where table_schema='engine' and table_name = 'profile'",
    )
    assert tables == []
