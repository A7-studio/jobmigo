import pytest
from fastapi import FastAPI

from engine.config import Settings
from engine.main import create_app

TOKEN = "t" * 40


@pytest.fixture
def settings() -> Settings:
    return Settings(
        engine_token=TOKEN,
        database_url="postgresql://user:pass@localhost:1/none",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def db_url() -> str:
    """A clean, migrated-from-scratch `_test` database."""
    from tests.db import ensure_database, reset_schemas, test_database_url

    url = test_database_url()
    await ensure_database(url)
    await reset_schemas(url)
    return url
