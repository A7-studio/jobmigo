"""The profile routes through the ASGI app."""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from engine.config import Settings
from engine.main import create_app
from tests.conftest import TOKEN
from tests.db import upgrade
from tests.profile_seed import seed_profile
from tests.test_cv_routes import USER_A, USER_B, auth, http


@pytest.fixture
async def app(db_url: str) -> AsyncIterator[FastAPI]:
    await upgrade(db_url)
    application = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    yield application
    await application.state.database.dispose()


async def test_the_full_flow_over_http(app: FastAPI, db_url: str) -> None:
    seeded = await seed_profile(db_url, USER_A)
    skill = f"/internal/profile/items/skill/{seeded.skill_ids[0]}"
    async with http(app) as client:
        edited = await client.patch(skill, headers=auth(), json={"name": "Flutter 3"})
        assert edited.status_code == 200
        assert edited.json()["status"] == "edited"

        confirmed = await client.post(
            f"/internal/profile/items/experience/{seeded.experience_ids[0]}/confirm",
            headers=auth(),
        )
        assert confirmed.json()["status"] == "confirmed"

        added = await client.post(
            "/internal/profile/items/project",
            headers=auth(),
            json={"name": "Open source", "description": "A library"},
        )
        assert added.status_code == 201
        assert added.json()["status"] == "edited"

        removed = await client.delete(
            f"/internal/profile/items/education/{seeded.education_ids[0]}",
            headers=auth(),
        )
        assert removed.status_code == 204 and removed.content == b""

        text = await client.patch(
            "/internal/profile", headers=auth(), json={"headline": "Mobile engineer"}
        )
        assert text.json()["headline"] == "Mobile engineer"

        done = await client.post("/internal/profile/confirm-all", headers=auth())
        assert done.status_code == 200
        assert (
            done.json()["confirmed"] == 4
        )  # a job, a skill, the achievement, the original project

        profile = (await client.get("/internal/profile", headers=auth())).json()
    assert profile["version"] == done.json()["version"]
    assert all(
        row["status"] in ("confirmed", "edited")
        for key in ("experiences", "skills", "achievements", "projects", "education")
        for row in profile[key]
    )


async def test_missing_malformed_foreign_and_old_ids_share_one_404(
    app: FastAPI, db_url: str
) -> None:
    mine = await seed_profile(db_url, USER_A)
    bodies = set()
    async with http(app) as client:
        for who, kind, item in (
            (USER_A, "skill", str(uuid.uuid4())),
            (USER_A, "skill", "not-a-uuid"),
            (USER_A, "job", str(mine.skill_ids[0])),
            (USER_B, "skill", str(mine.skill_ids[0])),
        ):
            for method, suffix in (("PATCH", ""), ("POST", "/confirm"), ("DELETE", "")):
                response = await client.request(
                    method,
                    f"/internal/profile/items/{kind}/{item}{suffix}",
                    headers=auth(who),
                    json={"name": "x"} if method == "PATCH" else None,
                )
                assert response.status_code == 404
                bodies.add(response.text)
    assert len(bodies) == 1


@pytest.mark.parametrize(
    "send",
    [
        {"content": b"not json"},
        {"content": b"[1,2]"},
        {"json": {}},
        {"json": {"unknown": "secret-text-xyz"}},
        {"json": {"name": "x" * 500}},
    ],
)
async def test_bad_bodies_are_a_stable_422_that_never_echoes_input(
    app: FastAPI, db_url: str, send: dict[str, object]
) -> None:
    seeded = await seed_profile(db_url, USER_A)
    async with http(app) as client:
        response = await client.patch(
            f"/internal/profile/items/skill/{seeded.skill_ids[0]}",
            headers=auth() | {"content-type": "application/json"},
            **send,  # type: ignore[arg-type]
        )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
    assert "secret-text-xyz" not in response.text and "xxxx" not in response.text


async def test_an_oversized_body_is_refused(app: FastAPI, db_url: str) -> None:
    await seed_profile(db_url, USER_A)
    async with http(app) as client:
        response = await client.post(
            "/internal/profile/items/skill",
            headers=auth(),
            json={"name": "a" * 40_000},
        )
    assert response.status_code == 422


async def test_duplicates_and_limits_have_stable_codes(
    app: FastAPI, db_url: str
) -> None:
    await seed_profile(db_url, USER_A)
    async with http(app) as client:
        duplicate = await client.post(
            "/internal/profile/items/skill", headers=auth(), json={"name": "dart"}
        )
    assert (duplicate.status_code, duplicate.json()["code"]) == (409, "already_exists")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("PATCH", "/internal/profile"),
        ("POST", "/internal/profile/confirm-all"),
        ("POST", "/internal/profile/items/skill"),
        ("PATCH", f"/internal/profile/items/skill/{uuid.uuid4()}"),
        ("POST", f"/internal/profile/items/skill/{uuid.uuid4()}/confirm"),
        ("DELETE", f"/internal/profile/items/skill/{uuid.uuid4()}"),
    ],
)
async def test_every_route_requires_the_token(
    app: FastAPI, method: str, path: str
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://engine.test"
    ) as client:
        response = await client.request(method, path, json={})
    assert response.status_code == 401


async def test_a_deeply_nested_body_is_a_422_not_a_500(
    app: FastAPI, db_url: str
) -> None:
    await seed_profile(db_url, USER_A)
    nested = b"[" * 20_000 + b"]" * 20_000
    async with http(app) as client:
        response = await client.patch(
            "/internal/profile",
            headers=auth() | {"content-type": "application/json"},
            content=nested,
        )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"


async def test_an_oversized_streamed_body_is_refused_without_a_length_header(
    app: FastAPI, db_url: str
) -> None:
    await seed_profile(db_url, USER_A)

    async def chunks() -> AsyncIterator[bytes]:
        yield b'{"headline": "'
        for _ in range(10):
            yield b"a" * 8_000
        yield b'"}'

    async with http(app) as client:
        response = await client.patch(
            "/internal/profile",
            headers=auth() | {"content-type": "application/json"},
            content=chunks(),
        )
    assert response.status_code == 422
