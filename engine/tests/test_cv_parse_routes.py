"""The parse routes through the ASGI app, with a fake provider and a real database."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from engine.ai.errors import AiUnavailableError
from engine.config import Settings
from engine.main import create_app
from engine.storage import MemoryStore
from tests.conftest import TOKEN
from tests.cv_fixtures import make_pdf
from tests.db import upgrade
from tests.test_ai_gateway import ENV, Fake, reply
from tests.test_cv_parse import GOOD
from tests.test_cv_routes import USER_A, USER_B, auth, http, in_process, named

CALLS = (("GET", ""), ("POST", "/parse"), ("GET", "/profile"))


@pytest.fixture
async def app(db_url: str) -> AsyncIterator[FastAPI]:
    await upgrade(db_url)
    application = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    application.state.object_store = MemoryStore()
    application.state.extractor = in_process
    application.state.ai_env = ENV
    yield application
    await application.state.parse_jobs.shutdown()
    await application.state.database.dispose()


def good() -> object:
    return reply(json.dumps(GOOD))


async def upload(app: FastAPI, user: uuid.UUID = USER_A) -> str:
    async with http(app) as client:
        response = await client.post(
            "/internal/cv", content=make_pdf(["Jane"]), headers=named(user)
        )
    assert response.status_code == 201
    return str(response.json()["id"])


async def settle(app: FastAPI) -> None:
    await asyncio.gather(*app.state.parse_jobs._tasks)


async def test_start_poll_and_read_the_draft(app: FastAPI) -> None:
    app.state.ai_provider = Fake(good())  # type: ignore[arg-type]
    cv = await upload(app)
    async with http(app) as client:
        started = await client.post(f"/internal/cv/{cv}/parse", headers=auth())
        assert started.status_code == 202
        assert started.json()["parseStatus"] == "parsing"
        assert started.json()["parseError"] is None
        await settle(app)

        status = await client.get(f"/internal/cv/{cv}", headers=auth())
        assert status.json()["parseStatus"] == "parsed"
        assert set(status.json()) == {
            "id",
            "filename",
            "mime",
            "sizeBytes",
            "parseStatus",
            "parseError",
            "createdAt",
        }

        draft = await client.get(f"/internal/cv/{cv}/profile", headers=auth())
        assert draft.status_code == 200
        body = draft.json()
        assert body["cvId"] == cv
        assert body["headline"] == "Flutter engineer"
        assert body["experiences"][0]["isCurrent"] is True
        assert body["experiences"][0]["status"] == "extracted"
        assert [s["name"] for s in body["skills"]] == ["Dart", "Flutter"]
        assert body["achievements"][0]["experienceId"] == body["experiences"][0]["id"]
        assert set(body) == {
            "id",
            "cvId",
            "headline",
            "summary",
            "experiences",
            "skills",
            "achievements",
            "projects",
            "education",
        }

        again = await client.post(f"/internal/cv/{cv}/parse", headers=auth())
        assert again.status_code == 200
        assert again.json()["parseStatus"] == "parsed"


async def test_a_failure_is_visible_in_status_and_list_and_a_retry_recovers(
    app: FastAPI,
) -> None:
    app.state.ai_provider = Fake(AiUnavailableError())
    cv = await upload(app)
    async with http(app) as client:
        await client.post(f"/internal/cv/{cv}/parse", headers=auth())
        await settle(app)
        failed = (await client.get(f"/internal/cv/{cv}", headers=auth())).json()
        assert (failed["parseStatus"], failed["parseError"]) == (
            "failed",
            "ai_unavailable",
        )
        listed = (await client.get("/internal/cv", headers=auth())).json()["items"]
        assert listed[0]["parseError"] == "ai_unavailable"
        assert (
            await client.get(f"/internal/cv/{cv}/profile", headers=auth())
        ).status_code == 404

        app.state.ai_provider = Fake(good())  # type: ignore[arg-type]
        retry = await client.post(f"/internal/cv/{cv}/parse", headers=auth())
        assert retry.status_code == 202
        assert retry.json()["parseError"] is None
        await settle(app)
        done = (await client.get(f"/internal/cv/{cv}", headers=auth())).json()
        assert (done["parseStatus"], done["parseError"]) == ("parsed", None)


async def test_missing_ai_configuration_is_a_503_and_changes_nothing(
    app: FastAPI,
) -> None:
    app.state.ai_env = {}
    cv = await upload(app)
    async with http(app) as client:
        response = await client.post(f"/internal/cv/{cv}/parse", headers=auth())
        assert response.status_code == 503
        assert response.json()["code"] == "ai_not_configured"
        status = await client.get(f"/internal/cv/{cv}", headers=auth())
        assert status.json()["parseStatus"] == "extracted"


async def test_the_draft_is_not_found_before_the_parse_finishes(app: FastAPI) -> None:
    cv = await upload(app)
    async with http(app) as client:
        response = await client.get(f"/internal/cv/{cv}/profile", headers=auth())
    assert response.status_code == 404


async def test_other_users_missing_and_malformed_ids_share_one_not_found_body(
    app: FastAPI,
) -> None:
    app.state.ai_provider = Fake(good())  # type: ignore[arg-type]
    cv = await upload(app)
    bodies = set()
    async with http(app) as client:
        for who, target in (
            (USER_B, cv),
            (USER_A, str(uuid.uuid4())),
            (USER_A, "not-a-uuid"),
        ):
            for method, suffix in (
                ("GET", ""),
                ("POST", "/parse"),
                ("GET", "/profile"),
            ):
                response = await client.request(
                    method, f"/internal/cv/{target}{suffix}", headers=auth(who)
                )
                assert response.status_code == 404
                bodies.add(response.text)
        status = await client.get(f"/internal/cv/{cv}", headers=auth())
    assert len(bodies) == 1
    assert status.json()["parseStatus"] == "extracted"


@pytest.mark.parametrize(("method", "suffix"), CALLS)
async def test_the_new_routes_require_the_token(
    app: FastAPI, method: str, suffix: str
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://engine.test"
    ) as client:
        response = await client.request(method, f"/internal/cv/{uuid.uuid4()}{suffix}")
    assert response.status_code == 401
