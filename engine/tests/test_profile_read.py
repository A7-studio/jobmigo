"""The profile read: the user's latest parsed draft."""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI

from engine.config import Settings
from engine.main import create_app
from tests.conftest import TOKEN
from tests.db import downgrade, fetch, upgrade
from tests.profile_seed import seed_profile
from tests.test_cv_routes import USER_A, USER_B, auth, http


@pytest.fixture
async def app(db_url: str) -> AsyncIterator[FastAPI]:
    await upgrade(db_url)
    application = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    yield application
    await application.state.database.dispose()


async def test_a_new_draft_starts_at_version_one(app: FastAPI, db_url: str) -> None:
    await seed_profile(db_url, USER_A)
    async with http(app) as client:
        response = await client.get("/internal/profile", headers=auth())
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["headline"] == "Flutter engineer"
    assert [e["company"] for e in body["experiences"]] == ["Northwind", "Brightside"]
    assert body["experiences"][0]["status"] == "extracted"
    assert {
        "id",
        "cvId",
        "version",
        "headline",
        "summary",
        "experiences",
        "skills",
        "achievements",
        "projects",
        "education",
    } == set(body)


async def test_the_newest_parsed_cv_wins(app: FastAPI, db_url: str) -> None:
    await seed_profile(
        db_url, USER_A, created_at="2026-11-01T00:00:00Z", headline="Old"
    )
    newer = await seed_profile(
        db_url, USER_A, created_at="2026-11-05T00:00:00Z", headline="New"
    )
    await seed_profile(
        db_url,
        USER_A,
        created_at="2026-11-09T00:00:00Z",
        status="failed",
        with_rows=False,
    )
    async with http(app) as client:
        body = (await client.get("/internal/profile", headers=auth())).json()
    assert body["headline"] == "New"
    assert body["cvId"] == str(newer.cv_id)


async def test_nobody_elses_draft_and_no_draft_share_one_404(
    app: FastAPI, db_url: str
) -> None:
    await seed_profile(db_url, USER_A)
    async with http(app) as client:
        other = await client.get("/internal/profile", headers=auth(USER_B))
        nobody = await client.get("/internal/profile", headers=auth(uuid.uuid4()))
    assert other.status_code == nobody.status_code == 404
    assert other.text == nobody.text


async def test_the_older_endpoint_still_reads_a_draft(
    app: FastAPI, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER_A)
    async with http(app) as client:
        response = await client.get(
            f"/internal/cv/{seeded.cv_id}/profile", headers=auth()
        )
    assert response.status_code == 200
    assert response.json()["version"] == 1


async def test_the_route_requires_the_token(app: FastAPI) -> None:
    async with http(app) as client:
        response = await client.get("/internal/profile")
    assert response.status_code == 401


async def test_downgrade_removes_the_version_column(db_url: str) -> None:
    await upgrade(db_url)
    await downgrade(db_url)
    columns = await fetch(
        db_url,
        "select column_name from information_schema.columns "
        "where table_schema='engine' and table_name='profile' "
        "and column_name in ('version','updated_at')",
    )
    assert columns == []
