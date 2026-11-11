"""Opportunity types: job, gig and AI training on jobs and tracks."""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from engine.config import Settings
from engine.main import create_app
from tests.conftest import TOKEN
from tests.db import upgrade
from tests.test_cv_routes import USER_A, USER_B, auth, http
from tests.test_jobs_routes import add


@pytest.fixture
async def app(db_url: str) -> AsyncIterator[FastAPI]:
    await upgrade(db_url)
    application = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    yield application
    await application.state.database.dispose()


async def new_track(
    client: AsyncClient, name: str, user: uuid.UUID = USER_A, **extra: Any
) -> dict[str, Any]:
    r = await client.post(
        "/internal/tracks", headers=auth(user), json={"name": name, **extra}
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


async def gate(url: str, track_id: str) -> None:
    """Give a track a do-not-apply entry that removes the test job by code alone."""
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(
            "update engine.track set do_not_apply = array['Acme'] where id = $1",
            uuid.UUID(track_id),
        )
    finally:
        await connection.close()


async def test_the_columns_default_to_job_and_refuse_other_words(db_url: str) -> None:
    await upgrade(db_url)
    connection = await asyncpg.connect(db_url)
    try:
        user = uuid.uuid4()
        await connection.execute(
            "insert into engine.track (user_id, name) values ($1, 'T')", user
        )
        await connection.execute(
            "insert into engine.job (user_id, company, title, dedupe_key, description)"
            " values ($1, 'C', 'T', 'k', 'd')",
            user,
        )
        assert await connection.fetchval("select kind from engine.track") == "job"
        assert await connection.fetchval("select kind from engine.job") == "job"
        for statement in (
            "update engine.track set kind = 'side'",
            "update engine.job set kind = 'side'",
        ):
            with pytest.raises(asyncpg.CheckViolationError):
                await connection.execute(statement)
    finally:
        await connection.close()


async def test_a_job_is_saved_with_a_type_and_defaults_to_job(app: FastAPI) -> None:
    async with http(app) as client:
        plain = await add(client)
        gig = await add(client, company="Beta", kind="gig")
        training = await add(client, company="Gamma", kind="ai_training")
        listed = await client.get("/internal/jobs", headers=auth(USER_A))
    assert plain["kind"] == "job"
    assert gig["kind"] == "gig"
    assert training["kind"] == "ai_training"
    assert {j["company"]: j["kind"] for j in listed.json()} == {
        "Acme": "job",
        "Beta": "gig",
        "Gamma": "ai_training",
    }


async def test_an_unknown_type_is_refused_on_create(app: FastAPI) -> None:
    async with http(app) as client:
        r = await client.post(
            "/internal/jobs",
            headers=auth(USER_A),
            json={
                "company": "Acme",
                "title": "T",
                "text": "<p>Build mobile apps with Flutter.</p>",
                "kind": "side_hustle",
            },
        )
    assert r.status_code == 422


async def test_a_job_patch_changes_the_type_the_status_or_both(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        url = f"/internal/jobs/{job['id']}"
        r = await client.patch(url, headers=auth(USER_A), json={"kind": "gig"})
        assert r.status_code == 200, r.text
        assert (r.json()["kind"], r.json()["status"]) == ("gig", "saved")
        r = await client.patch(url, headers=auth(USER_A), json={"status": "dismissed"})
        assert (r.json()["kind"], r.json()["status"]) == ("gig", "dismissed")
        r = await client.patch(
            url, headers=auth(USER_A), json={"status": "saved", "kind": "ai_training"}
        )
        assert (r.json()["kind"], r.json()["status"]) == ("ai_training", "saved")


async def test_a_job_patch_with_nothing_or_nonsense_is_refused(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        url = f"/internal/jobs/{job['id']}"
        for body in ({}, {"kind": "nope"}, {"kind": None, "status": None}, {"x": 1}):
            r = await client.patch(url, headers=auth(USER_A), json=body)
            assert r.status_code == 422, body


async def test_another_users_job_type_cannot_be_changed(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        r = await client.patch(
            f"/internal/jobs/{job['id']}", headers=auth(USER_B), json={"kind": "gig"}
        )
    assert r.status_code == 404


async def test_a_new_track_starts_with_preferences_for_its_type(app: FastAPI) -> None:
    async with http(app) as client:
        job_track = await new_track(client, "Jobs")
        gig = await new_track(client, "Gigs", kind="gig")
        training = await new_track(client, "Training", kind="ai_training")
    assert job_track["kind"] == "job"
    assert job_track["preferences"]["workModes"] == []
    assert gig["kind"] == "gig"
    assert gig["preferences"]["workModes"] == ["remote"]
    assert training["kind"] == "ai_training"
    assert training["preferences"]["workModes"] == ["remote"]


async def test_an_unknown_track_type_is_refused_and_a_rename_cannot_change_it(
    app: FastAPI,
) -> None:
    async with http(app) as client:
        bad = await client.post(
            "/internal/tracks", headers=auth(USER_A), json={"name": "X", "kind": "z"}
        )
        assert bad.status_code == 422
        track = await new_track(client, "Gigs", kind="gig")
        renamed = await client.patch(
            f"/internal/tracks/{track['id']}",
            headers=auth(USER_A),
            json={"name": "Gigs 2"},
        )
        assert renamed.status_code == 200
        assert (renamed.json()["name"], renamed.json()["kind"]) == ("Gigs 2", "gig")
        retyped = await client.patch(
            f"/internal/tracks/{track['id']}",
            headers=auth(USER_A),
            json={"name": "Gigs 3", "kind": "job"},
        )
        assert retyped.status_code == 422
        listed = await client.get("/internal/tracks", headers=auth(USER_A))
    assert [t["kind"] for t in listed.json()] == ["gig"]


async def test_a_job_is_screened_only_by_tracks_of_its_own_type(
    app: FastAPI, db_url: str
) -> None:
    async with http(app) as client:
        job_track = await new_track(client, "Jobs")
        gig_track = await new_track(client, "Gigs", kind="gig")
        await gate(db_url, job_track["id"])
        await gate(db_url, gig_track["id"])
        gig = await add(client, kind="gig")
        r = await client.post(
            f"/internal/jobs/{gig['id']}/screen", headers=auth(USER_A)
        )
        assert r.status_code == 200, r.text
        assert [s["trackId"] for s in r.json()] == [gig_track["id"]]
        plain = await add(client, company="Beta")
        r = await client.post(
            f"/internal/jobs/{plain['id']}/screen", headers=auth(USER_A)
        )
        assert [s["trackId"] for s in r.json()] == [job_track["id"]]


async def test_results_for_another_type_are_hidden_not_deleted(
    app: FastAPI, db_url: str
) -> None:
    async with http(app) as client:
        job_track = await new_track(client, "Jobs")
        await gate(db_url, job_track["id"])
        job = await add(client)
        url = f"/internal/jobs/{job['id']}"
        first = await client.post(f"{url}/screen", headers=auth(USER_A))
        assert len(first.json()) == 1
        await client.patch(url, headers=auth(USER_A), json={"kind": "gig"})
        hidden = await client.get(f"{url}/screens", headers=auth(USER_A))
        assert hidden.json() == []
        await client.patch(url, headers=auth(USER_A), json={"kind": "job"})
        back = await client.get(f"{url}/screens", headers=auth(USER_A))
        assert [s["trackId"] for s in back.json()] == [job_track["id"]]
        assert back.json()[0]["id"] == first.json()[0]["id"]


async def test_evaluating_with_a_track_of_another_type_is_refused(
    app: FastAPI,
) -> None:
    async with http(app) as client:
        gig_track = await new_track(client, "Gigs", kind="gig")
        job = await add(client)
        r = await client.post(
            f"/internal/jobs/{job['id']}/evaluate",
            headers=auth(USER_A),
            json={"trackId": gig_track["id"]},
        )
        listed = await client.get(
            f"/internal/jobs/{job['id']}/evaluations", headers=auth(USER_A)
        )
    assert r.status_code == 422
    assert r.json()["code"] == "wrong_type"
    assert listed.json() == []
