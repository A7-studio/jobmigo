"""The kit routes through the ASGI app.

No model is reachable here, so only the saved-row shape and the refusals are tested; the
writing itself is covered with a fake provider in `test_kitting.py`.
"""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
from fastapi import FastAPI

from engine.config import Settings
from engine.main import create_app
from tests.conftest import TOKEN
from tests.db import upgrade
from tests.profile_seed import seed_profile
from tests.test_cv_routes import USER_A, USER_B, auth, http
from tests.test_jobs_routes import add


@pytest.fixture
async def app(db_url: str) -> AsyncIterator[FastAPI]:
    await upgrade(db_url)
    application = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    yield application
    await application.state.database.dispose()


async def run(url: str, query: str, *args: object) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()


async def add_track(url: str, user: uuid.UUID, name: str = "Mobile") -> str:
    track = uuid.uuid4()
    await run(
        url,
        "insert into engine.track (id, user_id, name) values ($1, $2, $3)",
        track,
        user,
        name,
    )
    return str(track)


async def save_version(
    url: str, user: uuid.UUID, job: str, track: str, profile: uuid.UUID, version: int
) -> None:
    content = {"docType": "cv", "summary": {"text": "t", "sources": [], "flags": []}}
    await run(
        url,
        "insert into engine.kit_version (user_id, job_id, track_id, profile_id,"
        " profile_version, doc_type, version, cache_key, content, fact_check)"
        " values ($1, $2, $3, $4, 1, 'cv', $5, 'k', $6::jsonb, $7::jsonb)",
        user,
        uuid.UUID(job),
        uuid.UUID(track),
        profile,
        version,
        json.dumps(content),
        json.dumps({"blocks": 1, "flagged": 0, "flags": []}),
    )


async def test_saved_versions_are_listed_with_the_stable_shape(
    app: FastAPI, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER_A)
    async with http(app) as client:
        job = await add(client)
        track = await add_track(db_url, USER_A)
        await save_version(db_url, USER_A, job["id"], track, seeded.profile_id, 1)
        await save_version(db_url, USER_A, job["id"], track, seeded.profile_id, 2)
        latest = await client.get(
            f"/internal/jobs/{job['id']}/kits", headers=auth(USER_A)
        )
        every = await client.get(
            f"/internal/jobs/{job['id']}/kits?trackId={track}", headers=auth(USER_A)
        )
    assert latest.status_code == 200, latest.text
    rows: list[dict[str, Any]] = latest.json()
    assert [r["version"] for r in rows] == [2]
    assert set(rows[0]) == {
        "id",
        "jobId",
        "trackId",
        "trackName",
        "docType",
        "version",
        "profileVersion",
        "stale",
        "content",
        "factCheck",
        "createdAt",
    }
    assert rows[0]["trackName"] == "Mobile"
    assert [r["version"] for r in every.json()] == [2, 1]


async def test_a_job_with_no_kit_lists_none(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        r = await client.get(f"/internal/jobs/{job['id']}/kits", headers=auth(USER_A))
    assert r.status_code == 200 and r.json() == []


async def test_a_made_up_or_foreign_job_or_track_is_not_found(
    app: FastAPI, db_url: str
) -> None:
    await seed_profile(db_url, USER_B)
    async with http(app) as client:
        theirs = await add(client, USER_B)
        mine = await add(client, company="Mine")
        their_track = await add_track(db_url, USER_B)
        for path in (
            f"/internal/jobs/{uuid.uuid4()}/kits",
            f"/internal/jobs/{theirs['id']}/kits",
            "/internal/jobs/not-a-uuid/kits",
            f"/internal/jobs/{mine['id']}/kits?trackId=not-a-uuid",
        ):
            r = await client.get(path, headers=auth(USER_A))
            assert r.status_code == 404, path
        for job, track in ((uuid.uuid4(), their_track), (mine["id"], their_track)):
            r = await client.post(
                f"/internal/jobs/{job}/kit",
                headers=auth(USER_A),
                json={"trackId": str(track)},
            )
            assert r.status_code == 404, (job, track)


async def test_a_bad_body_is_refused_before_anything_runs(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        for body in ({}, {"trackId": "x"}, {"trackId": str(uuid.uuid4()), "q": 1}):
            r = await client.post(
                f"/internal/jobs/{job['id']}/kit", headers=auth(USER_A), json=body
            )
            assert r.status_code == 422, body
            assert set(r.json()) == {"code", "message"}


async def test_a_user_with_no_confirmed_facts_is_asked_to_confirm(
    app: FastAPI, db_url: str
) -> None:
    await seed_profile(db_url, USER_A)
    async with http(app) as client:
        job = await add(client)
        track = await add_track(db_url, USER_A)
        r = await client.post(
            f"/internal/jobs/{job['id']}/kit",
            headers=auth(USER_A),
            json={"trackId": track},
        )
    assert r.status_code == 409
    assert r.json()["code"] == "no_confirmed_profile"


async def test_the_routes_need_the_engine_token(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        for method, path in (
            ("GET", f"/internal/jobs/{job['id']}/kits"),
            ("POST", f"/internal/jobs/{job['id']}/kit"),
        ):
            r = await client.request(method, path)
            assert r.status_code == 401


async def test_editing_needs_the_token_and_refuses_a_made_up_or_foreign_kit(
    app: FastAPI, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER_B)
    async with http(app) as client:
        theirs = await add(client, USER_B)
        their_track = await add_track(db_url, USER_B)
        await save_version(
            db_url, USER_B, theirs["id"], their_track, seeded.profile_id, 1
        )
        listed = await client.get(
            f"/internal/jobs/{theirs['id']}/kits", headers=auth(USER_B)
        )
        kit_id = listed.json()[0]["id"]
        body = {"path": "summary", "action": "edit", "text": "x"}
        refused = await client.patch(
            f"/internal/jobs/{theirs['id']}/kits/{kit_id}", json=body
        )
        assert refused.status_code == 401
        for job, kit in ((theirs["id"], kit_id), (theirs["id"], str(uuid.uuid4()))):
            r = await client.patch(
                f"/internal/jobs/{job}/kits/{kit}", headers=auth(USER_A), json=body
            )
            assert r.status_code == 404, (job, kit)
        r = await client.patch(
            f"/internal/jobs/{theirs['id']}/kits/{kit_id}",
            headers=auth(USER_B),
            json={"path": "summary", "action": "burn"},
        )
        assert r.status_code == 422
        assert set(r.json()) == {"code", "message"}


async def test_an_edit_is_saved_as_the_next_version_through_the_route(
    app: FastAPI, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER_A)
    async with http(app) as client:
        job = await add(client)
        track = await add_track(db_url, USER_A)
        await save_version(db_url, USER_A, job["id"], track, seeded.profile_id, 1)
        first = (
            await client.get(f"/internal/jobs/{job['id']}/kits", headers=auth(USER_A))
        ).json()[0]
        r = await client.patch(
            f"/internal/jobs/{job['id']}/kits/{first['id']}",
            headers=auth(USER_A),
            json={"path": "summary", "action": "edit", "text": "My own words."},
        )
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    assert body["version"] == 2
    assert body["content"]["summary"]["text"] == "My own words."
    assert body["content"]["summary"]["edited"] is True
    assert set(body) == set(first)


async def save_sourced_cv(
    url: str, user: uuid.UUID, job: str, track: str, seeded: Any
) -> str:
    """A saved CV whose one statement cites a skill fact the person has confirmed."""
    skill = seeded.skill_ids[0]
    await run(
        url,
        "update engine.skill set status = 'confirmed' where id = $1",
        skill,
    )
    content = {
        "docType": "cv",
        "summary": {
            "text": "Flutter.",
            "sources": [{"label": "S1", "kind": "skill", "id": str(skill)}],
            "flags": [],
            "numbers": [],
        },
        "entries": [],
        "skills": [],
    }
    row = uuid.uuid4()
    await run(
        url,
        "insert into engine.kit_version (id, user_id, job_id, track_id, profile_id,"
        " profile_version, doc_type, version, cache_key, content, fact_check)"
        " values ($1, $2, $3, $4, $5, 1, 'cv', 1, 'k', $6::jsonb, $7::jsonb)",
        row,
        user,
        uuid.UUID(job),
        uuid.UUID(track),
        seeded.profile_id,
        json.dumps(content),
        json.dumps({"blocks": 1, "flagged": 0, "flags": [], "omitted": 0}),
    )
    return str(row)


async def test_a_checked_kit_exports_as_json_with_the_file_in_base64(
    app: FastAPI, db_url: str
) -> None:
    import base64

    seeded = await seed_profile(db_url, USER_A)
    async with http(app) as client:
        job = await add(client)
        track = await add_track(db_url, USER_A)
        kit = await save_sourced_cv(db_url, USER_A, job["id"], track, seeded)
        r = await client.post(
            f"/internal/jobs/{job['id']}/kits/{kit}/export",
            headers=auth(USER_A),
            json={"format": "pdf", "name": "Sam Gichu", "contact": "sam@example.com"},
        )
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    assert set(body) == {"filename", "contentType", "data"}
    assert body["contentType"] == "application/pdf"
    assert body["filename"] == "Sam Gichu - CV - Acme.pdf"
    assert base64.b64decode(body["data"]).startswith(b"%PDF")


async def test_a_flagged_kit_is_refused_with_409_through_the_route(
    app: FastAPI, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER_A)  # nothing confirmed: sources are gone
    async with http(app) as client:
        job = await add(client)
        track = await add_track(db_url, USER_A)
        await save_version(db_url, USER_A, job["id"], track, seeded.profile_id, 1)
        first = (
            await client.get(f"/internal/jobs/{job['id']}/kits", headers=auth(USER_A))
        ).json()[0]
        r = await client.post(
            f"/internal/jobs/{job['id']}/kits/{first['id']}/export",
            headers=auth(USER_A),
            json={"format": "docx", "name": "Sam"},
        )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "needs_fixing"
    assert set(r.json()) == {"code", "message"}


async def test_export_needs_the_token_and_refuses_foreign_and_bad_requests(
    app: FastAPI, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER_B)
    async with http(app) as client:
        theirs = await add(client, USER_B)
        their_track = await add_track(db_url, USER_B)
        kit = await save_sourced_cv(db_url, USER_B, theirs["id"], their_track, seeded)
        path = f"/internal/jobs/{theirs['id']}/kits/{kit}/export"
        body = {"format": "pdf", "name": "Sam"}
        assert (await client.post(path, json=body)).status_code == 401
        assert (
            await client.post(path, headers=auth(USER_A), json=body)
        ).status_code == 404
        for bad in (
            {},
            {"format": "exe", "name": "Sam"},
            {"format": "pdf", "name": ""},
        ):
            r = await client.post(path, headers=auth(USER_B), json=bad)
            assert r.status_code == 422, bad
            assert set(r.json()) == {"code", "message"}
        ok = await client.post(path, headers=auth(USER_B), json=body)
        assert ok.status_code == 200, ok.text
