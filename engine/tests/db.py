"""Helpers for tests that need Postgres. They only ever touch a `_test` database."""

import asyncio
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parent.parent
TEST_DB_SUFFIX = "_test"


def require_test_database(url: str | None) -> str:
    """Return the URL, or refuse: tests must never touch a real database."""
    if not url:
        raise RuntimeError("Missing environment variable ENGINE_TEST_DATABASE_URL.")
    name = urlsplit(url).path.lstrip("/")
    if not name.endswith(TEST_DB_SUFFIX):
        raise RuntimeError(
            f'Refusing to run tests: database "{name}" must end in "{TEST_DB_SUFFIX}".'
        )
    return url


def test_database_url() -> str:
    return require_test_database(os.environ.get("ENGINE_TEST_DATABASE_URL"))


async def ensure_database(url: str) -> None:
    """Create the test database if it does not exist yet."""
    parts = urlsplit(url)
    name = parts.path.lstrip("/")
    admin = urlunsplit(parts._replace(path="/postgres"))
    connection = await asyncpg.connect(admin)
    try:
        exists = await connection.fetchval(
            "select 1 from pg_database where datname = $1", name
        )
        if not exists:
            await connection.execute(f'create database "{name}"')
    finally:
        await connection.close()


async def reset_schemas(url: str) -> None:
    """Start from nothing: drop the engine schema so migrations run from scratch."""
    connection = await asyncpg.connect(url)
    try:
        await connection.execute('drop schema if exists "engine" cascade')
    finally:
        await connection.close()


def alembic_config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


async def upgrade(url: str, revision: str = "head") -> None:
    # Alembic's environment runs its own event loop, so run it off this one.
    await asyncio.to_thread(command.upgrade, alembic_config(url), revision)


async def downgrade(url: str, revision: str = "base") -> None:
    await asyncio.to_thread(command.downgrade, alembic_config(url), revision)


async def fetch(url: str, query: str, *args: object) -> list[dict[str, object]]:
    connection = await asyncpg.connect(url)
    try:
        rows = await connection.fetch(query, *args)
        result: list[dict[str, object]] = [dict(row) for row in rows]
        return result
    finally:
        await connection.close()
