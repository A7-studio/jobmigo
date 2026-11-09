import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from engine.config import Settings
from engine.main import create_app
from tests.conftest import TOKEN
from tests.db import downgrade, fetch, require_test_database, upgrade


def client(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://engine.test",
    )


def test_tests_refuse_a_database_that_is_not_a_test_database() -> None:
    for url in (
        "postgresql://u:p@localhost:5442/jobmigo",
        "postgresql://u:p@localhost:5442/jobmigo_testing",
    ):
        with pytest.raises(RuntimeError, match="must end in"):
            require_test_database(url)
    with pytest.raises(RuntimeError, match="ENGINE_TEST_DATABASE_URL"):
        require_test_database(None)
    assert require_test_database("postgresql://u:p@h/jobmigo_engine_test")


async def test_upgrade_creates_the_engine_schema_and_only_that(db_url: str) -> None:
    before = await fetch(
        db_url,
        "select table_name from information_schema.tables where table_schema='public'",
    )
    await upgrade(db_url)
    schemas = await fetch(
        db_url, "select 1 from information_schema.schemata where schema_name='engine'"
    )
    tables = await fetch(
        db_url,
        "select table_name from information_schema.tables where table_schema='engine'",
    )
    after = await fetch(
        db_url,
        "select table_name from information_schema.tables where table_schema='public'",
    )
    versions = await fetch(db_url, "select version_num from engine.alembic_version")
    assert len(schemas) == 1
    assert sorted(str(row["table_name"]) for row in tables) == [
        "achievement",
        "ai_cache",
        "alembic_version",
        "cv_file",
        "education",
        "experience",
        "profile",
        "project",
        "skill",
        "usage_event",
    ]
    assert [row["version_num"] for row in versions] == ["0004"]
    assert [r["table_name"] for r in after] == [r["table_name"] for r in before]


async def test_upgrade_twice_is_a_no_op(db_url: str) -> None:
    await upgrade(db_url)
    await upgrade(db_url)
    versions = await fetch(db_url, "select version_num from engine.alembic_version")
    assert [row["version_num"] for row in versions] == ["0004"]


async def test_downgrade_returns_to_an_empty_version_table(db_url: str) -> None:
    await upgrade(db_url)
    await downgrade(db_url)
    versions = await fetch(db_url, "select version_num from engine.alembic_version")
    assert versions == []
    await upgrade(db_url)
    again = await fetch(db_url, "select version_num from engine.alembic_version")
    assert [row["version_num"] for row in again] == ["0004"]


async def test_readyz_is_ready_when_the_database_answers(db_url: str) -> None:
    app = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    async with client(app) as http:
        response = await http.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    await app.state.database.dispose()


async def test_readyz_is_503_without_detail_when_it_does_not() -> None:
    app = create_app(
        Settings(
            engine_token=TOKEN,
            database_url="postgresql://nobody:secret-pass@127.0.0.1:1/missing",
        )
    )
    async with client(app) as http:
        response = await http.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"code": "not_ready", "message": "Not ready."}
    assert "secret-pass" not in response.text
    await app.state.database.dispose()
