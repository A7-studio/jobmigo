"""Ports of the 'ai ledger tables' cases in web/tests/schema.test.ts."""

import uuid

import asyncpg
import pytest

from tests.db import downgrade, fetch, upgrade

INSERT_EVENT = """
insert into engine.usage_event
  (user_id, workflow, provider, model, prompt_version, tokens_in, tokens_out, cache_hit)
values ($1, $2, 'p', 'm', 'v1', $3, 0, false)
"""
INSERT_CACHE = """
insert into engine.ai_cache (user_id, cache_key, task, prompt_version, output)
values ($1, $2, 't', 'v1', '{}'::jsonb)
"""


async def run(url: str, query: str, *args: object) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()


async def test_the_ledger_and_cache_have_the_documented_columns(db_url: str) -> None:
    await upgrade(db_url)
    rows = await fetch(
        db_url,
        "select table_name, column_name from information_schema.columns "
        "where table_schema = 'engine' and table_name in ('usage_event', 'ai_cache') "
        "order by table_name, ordinal_position",
    )
    columns: dict[str, list[object]] = {}
    for row in rows:
        columns.setdefault(str(row["table_name"]), []).append(row["column_name"])
    assert columns["usage_event"] == [
        "id",
        "user_id",
        "workflow",
        "provider",
        "model",
        "prompt_version",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "cache_hit",
        "created_at",
    ]
    assert columns["ai_cache"] == [
        "user_id",
        "cache_key",
        "task",
        "prompt_version",
        "output",
        "created_at",
    ]
    indexes = await fetch(
        db_url,
        "select indexname from pg_indexes where schemaname = 'engine' "
        "and tablename = 'usage_event'",
    )
    assert "usage_event_user_created_idx" in [row["indexname"] for row in indexes]


async def test_rejects_an_unknown_workflow(db_url: str) -> None:
    # 'rejects an unknown workflow'
    await upgrade(db_url)
    with pytest.raises(asyncpg.CheckViolationError, match="ck_usage_event_workflow"):
        await run(db_url, INSERT_EVENT, uuid.uuid4(), "chat", 1)


async def test_rejects_negative_token_counts(db_url: str) -> None:
    # 'rejects negative token counts'
    await upgrade(db_url)
    with pytest.raises(asyncpg.CheckViolationError, match="ck_usage_event_tokens"):
        await run(db_url, INSERT_EVENT, uuid.uuid4(), "parse", -1)


async def test_allows_a_null_cost_and_one_cache_row_per_user_and_key(
    db_url: str,
) -> None:
    # 'allows a null cost ...' (rows are removed by user id later, not by a foreign key)
    await upgrade(db_url)
    user = uuid.uuid4()
    await run(db_url, INSERT_EVENT, user, "parse", 10)
    rows = await fetch(db_url, "select cost_usd from engine.usage_event")
    assert rows == [{"cost_usd": None}]
    await run(db_url, INSERT_CACHE, user, "k")
    await run(db_url, INSERT_CACHE, uuid.uuid4(), "k")  # another user, same key
    with pytest.raises(asyncpg.UniqueViolationError):
        await run(db_url, INSERT_CACHE, user, "k")


async def test_downgrade_removes_both_tables(db_url: str) -> None:
    await upgrade(db_url)
    await downgrade(db_url, "0001")
    tables = await fetch(
        db_url,
        "select table_name from information_schema.tables where table_schema='engine'",
    )
    assert [row["table_name"] for row in tables] == ["alembic_version"]
