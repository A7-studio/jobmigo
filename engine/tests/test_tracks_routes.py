"""The track routes through the ASGI app."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from engine.config import Settings
from engine.main import create_app
from tests.conftest import TOKEN
from tests.db import fetch, upgrade
from tests.profile_seed import Seeded, seed_profile
from tests.test_cv_routes import USER_A, USER_B, auth, http


@pytest.fixture
async def app(db_url: str) -> AsyncIterator[FastAPI]:
    await upgrade(db_url)
    application = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    yield application
    await application.state.database.dispose()


async def make(
    client: AsyncClient, name: str, user: uuid.UUID = USER_A
) -> dict[str, Any]:
    created = await client.post(
        "/internal/tracks", headers=auth(user), json={"name": name}
    )
    assert created.status_code == 201, created.text
    result: dict[str, Any] = created.json()
    return result


def fact(seeded: Seeded, kind: str = "skill") -> str:
    ids = {
        "skill": seeded.skill_ids,
        "experience": seeded.experience_ids,
        "project": seeded.project_ids,
    }
    return str(ids[kind][0])


async def confirm(client: AsyncClient, kind: str, item: str) -> None:
    done = await client.post(
        f"/internal/profile/items/{kind}/{item}/confirm", headers=auth()
    )
    assert done.status_code == 200


async def test_create_list_rename_delete(app: FastAPI) -> None:
    async with http(app) as client:
        assert (await client.get("/internal/tracks", headers=auth())).json() == []
        first = await make(client, "Flutter  and\tmobile")
        assert first["name"] == "Flutter and mobile"
        assert first["variantVersion"] == 1
        assert first["emphasis"] == []
        second = await make(client, "AI coding evaluation")
        listed = (await client.get("/internal/tracks", headers=auth())).json()
        assert [t["id"] for t in listed] == [first["id"], second["id"]]

        renamed = await client.patch(
            f"/internal/tracks/{first['id']}", headers=auth(), json={"name": "Mobile"}
        )
        assert renamed.json()["name"] == "Mobile"
        assert renamed.json()["variantVersion"] == 2
        same = await client.patch(
            f"/internal/tracks/{first['id']}", headers=auth(), json={"name": "Mobile"}
        )
        assert same.json()["variantVersion"] == 2

        gone = await client.delete(f"/internal/tracks/{first['id']}", headers=auth())
        assert gone.status_code == 204
        listed = (await client.get("/internal/tracks", headers=auth())).json()
        assert [t["id"] for t in listed] == [second["id"]]


async def test_names_are_validated_and_unique_ignoring_case(app: FastAPI) -> None:
    async with http(app) as client:
        for bad in (
            {},
            {"name": ""},
            {"name": "   "},
            {"name": "x" * 61},
            {"name": 5},
            {"name": "ok", "extra": 1},
        ):
            r = await client.post("/internal/tracks", headers=auth(), json=bad)
            assert r.status_code == 422, bad
            assert r.json()["code"] == "validation_failed"
        await make(client, "Mobile")
        dup = await client.post(
            "/internal/tracks", headers=auth(), json={"name": "MOBILE"}
        )
        assert dup.status_code == 409
        assert dup.json()["code"] == "already_exists"
        other = await make(client, "Mobile", USER_B)  # another user may reuse a name
        assert other["name"] == "Mobile"
        mine = await make(client, "Second")
        clash = await client.patch(
            f"/internal/tracks/{mine['id']}", headers=auth(), json={"name": "mobile"}
        )
        assert clash.status_code == 409


async def test_the_cap_is_ten_even_when_creates_race(app: FastAPI) -> None:
    async with http(app) as client:
        results = await asyncio.gather(
            *[
                client.post("/internal/tracks", headers=auth(), json={"name": f"T{i}"})
                for i in range(14)
            ]
        )
        codes = sorted(r.status_code for r in results)
        assert codes.count(201) == 10
        assert codes.count(422) == 4
        assert {r.json()["code"] for r in results if r.status_code == 422} == {
            "limit_reached"
        }
        assert len((await client.get("/internal/tracks", headers=auth())).json()) == 10


async def test_another_users_track_is_not_found(app: FastAPI, db_url: str) -> None:
    seeded = await seed_profile(db_url, USER_A)
    async with http(app) as client:
        track = await make(client, "Mine")
        item = fact(seeded)
        await confirm(client, "skill", item)
        url = f"/internal/tracks/{track['id']}"
        for method, path, body in (
            ("PATCH", url, {"name": "X"}),
            ("DELETE", url, None),
            ("PUT", f"{url}/items/skill/{item}", None),
            ("DELETE", f"{url}/items/skill/{item}", None),
        ):
            r = (
                await client.request(method, path, headers=auth(USER_B), json=body)
                if body
                else await client.request(method, path, headers=auth(USER_B))
            )
            assert r.status_code == 404, (method, path)
            assert r.json()["code"] == "not_found"
        assert (await client.get("/internal/tracks", headers=auth(USER_B))).json() == []


async def test_bad_ids_and_kinds_are_not_found(app: FastAPI) -> None:
    async with http(app) as client:
        track = await make(client, "Mine")
        for path in (
            "/internal/tracks/not-a-uuid",
            f"/internal/tracks/{uuid.uuid4()}",
        ):
            assert (await client.delete(path, headers=auth())).status_code == 404
        base = f"/internal/tracks/{track['id']}/items"
        for tail in (f"widget/{uuid.uuid4()}", "skill/not-a-uuid"):
            assert (
                await client.put(f"{base}/{tail}", headers=auth())
            ).status_code == 404


async def test_emphasis_needs_a_confirmed_fact_of_the_latest_profile(
    app: FastAPI, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER_A)
    async with http(app) as client:
        track = await make(client, "Mobile")
        base = f"/internal/tracks/{track['id']}/items"
        skill = fact(seeded)
        refused = await client.put(f"{base}/skill/{skill}", headers=auth())
        assert refused.status_code == 422
        assert refused.json()["code"] == "not_confirmed"
        missing = await client.put(f"{base}/skill/{uuid.uuid4()}", headers=auth())
        assert missing.status_code == 404

        await confirm(client, "skill", skill)
        on = await client.put(f"{base}/skill/{skill}", headers=auth())
        assert on.status_code == 200
        assert on.json()["emphasis"] == [{"kind": "skill", "itemId": skill}]
        assert on.json()["variantVersion"] == 2
        again = await client.put(f"{base}/skill/{skill}", headers=auth())
        assert again.json()["variantVersion"] == 2  # idempotent, no bump

        off = await client.delete(f"{base}/skill/{skill}", headers=auth())
        assert off.json()["emphasis"] == []
        assert off.json()["variantVersion"] == 3
        off_again = await client.delete(f"{base}/skill/{skill}", headers=auth())
        assert off_again.json()["variantVersion"] == 3

    other = await seed_profile(db_url, USER_B)
    async with http(app) as client:
        track_b = await make(client, "B", USER_B)
        # A fact of someone else's profile is never reachable.
        r = await client.put(
            f"/internal/tracks/{track_b['id']}/items/skill/{skill}",
            headers=auth(USER_B),
        )
        assert r.status_code == 404
        assert other.skill_ids


async def test_a_fact_of_an_older_draft_cannot_be_emphasised(
    app: FastAPI, db_url: str
) -> None:
    old = await seed_profile(db_url, USER_A, created_at="2026-10-01T00:00:00Z")
    await seed_profile(db_url, USER_A, created_at="2026-11-01T00:00:00Z")
    async with http(app) as client:
        track = await make(client, "Mobile")
        r = await client.put(
            f"/internal/tracks/{track['id']}/items/skill/{old.skill_ids[0]}",
            headers=auth(),
        )
        assert r.status_code == 404


async def test_deleting_a_track_or_a_fact_removes_the_emphasis(
    app: FastAPI, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER_A)
    async with http(app) as client:
        track = await make(client, "Mobile")
        other = await make(client, "Other")
        skill = fact(seeded)
        await confirm(client, "skill", skill)
        for t in (track, other):
            await client.put(
                f"/internal/tracks/{t['id']}/items/skill/{skill}", headers=auth()
            )
        count = "select count(*) as n from engine.track_profile_item"
        assert (await fetch(db_url, count))[0]["n"] == 2

        await client.delete(f"/internal/profile/items/skill/{skill}", headers=auth())
        assert (await fetch(db_url, count))[0]["n"] == 0

        project = fact(seeded, "project")
        await confirm(client, "project", project)
        await client.put(
            f"/internal/tracks/{track['id']}/items/project/{project}", headers=auth()
        )
        assert (await fetch(db_url, count))[0]["n"] == 1
        await client.delete(f"/internal/tracks/{track['id']}", headers=auth())
        assert (await fetch(db_url, count))[0]["n"] == 0


async def test_concurrent_emphasis_changes_each_count_once(
    app: FastAPI, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER_A)
    async with http(app) as client:
        track = await make(client, "Mobile")
        items = [str(seeded.skill_ids[0]), str(seeded.skill_ids[1])]
        for item in items:
            await confirm(client, "skill", item)
        results = await asyncio.gather(
            *[
                client.put(
                    f"/internal/tracks/{track['id']}/items/skill/{item}", headers=auth()
                )
                for item in items * 2
            ]
        )
        assert all(r.status_code == 200 for r in results)
        final = (await client.get("/internal/tracks", headers=auth())).json()[0]
        assert len(final["emphasis"]) == 2
        assert final["variantVersion"] == 3


async def test_unauthenticated_and_oversized_bodies_are_refused(app: FastAPI) -> None:
    async with http(app) as client:
        assert (await client.get("/internal/tracks")).status_code == 401
        big = await client.post(
            "/internal/tracks",
            headers=auth(),
            content=b'{"name":"' + b"x" * 40000 + b'"}',
        )
        assert big.status_code == 422
