"""The screen routes through the ASGI app.

Only tracks that a code gate removes are used, so no test here can reach a model.
"""

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
from tests.test_cv_routes import USER_A, USER_B, auth, http
from tests.test_jobs_routes import add


@pytest.fixture
async def app(db_url: str) -> AsyncIterator[FastAPI]:
    await upgrade(db_url)
    application = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    yield application
    await application.state.database.dispose()


async def add_gated_track(url: str, user: uuid.UUID, name: str = "Mobile") -> str:
    track = uuid.uuid4()
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(
            "insert into engine.track (id, user_id, name, do_not_apply) "
            "values ($1, $2, $3, array['Acme'])",
            track,
            user,
            name,
        )
    finally:
        await connection.close()
    return str(track)


async def test_screening_a_job_returns_and_saves_the_results(
    app: FastAPI, db_url: str
) -> None:
    async with http(app) as client:
        job = await add(client)
        track = await add_gated_track(db_url, USER_A)
        r = await client.post(
            f"/internal/jobs/{job['id']}/screen", headers=auth(USER_A)
        )
        assert r.status_code == 200, r.text
        body: list[dict[str, Any]] = r.json()
        assert len(body) == 1
        row = body[0]
        assert row["trackId"] == track
        assert row["jobId"] == job["id"]
        assert row["trackName"] == "Mobile"
        assert row["outcome"] == "removed"
        assert row["removedBy"] == "gate"
        assert row["reasonCode"] == "do_not_apply"
        assert "Acme" in row["reason"]
        assert row["stale"] is False
        assert row["screen"] is None
        assert set(row) == {
            "id",
            "jobId",
            "trackId",
            "trackName",
            "variantVersion",
            "stale",
            "outcome",
            "removedBy",
            "reasonCode",
            "reason",
            "screen",
            "updatedAt",
        }

        saved = await client.get(
            f"/internal/jobs/{job['id']}/screens", headers=auth(USER_A)
        )
        assert saved.status_code == 200
        assert saved.json() == body


async def test_a_job_with_no_results_yet_lists_none(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        r = await client.get(
            f"/internal/jobs/{job['id']}/screens", headers=auth(USER_A)
        )
        assert r.status_code == 200
        assert r.json() == []


async def test_a_made_up_or_foreign_job_is_not_found(app: FastAPI, db_url: str) -> None:
    async with http(app) as client:
        theirs = await add(client, user=USER_B)
        await add_gated_track(db_url, USER_A)
        for job_id in (str(uuid.uuid4()), "nope", theirs["id"]):
            for method, suffix in (("POST", "screen"), ("GET", "screens")):
                r = await client.request(
                    method,
                    f"/internal/jobs/{job_id}/{suffix}",
                    headers=auth(USER_A),
                )
                assert r.status_code == 404, (job_id, suffix, r.text)
                assert r.json() == {"code": "not_found", "message": "Not found."}


async def test_a_user_with_no_track_is_asked_to_create_one(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        r = await client.post(
            f"/internal/jobs/{job['id']}/screen", headers=auth(USER_A)
        )
        assert r.status_code == 409
        assert r.json() == {"code": "no_tracks", "message": "Create a track first."}


async def test_the_routes_need_the_engine_token(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        for method, suffix in (("POST", "screen"), ("GET", "screens")):
            r = await client.request(method, f"/internal/jobs/{job['id']}/{suffix}")
            assert r.status_code in (401, 403)


async def test_a_flagged_result_goes_through_the_route_as_a_flag_not_a_removal(
    app: FastAPI, db_url: str
) -> None:
    async with http(app) as client:
        job = await add(client)
        track = await add_gated_track(db_url, USER_A)
        await run_sql(
            db_url,
            "insert into engine.job_screen (user_id, job_id, track_id, "
            "variant_version, rules_key, outcome, reason_code, reason, screen) "
            "values ($1, $2, $3, 1, 'k', 'flagged', 'dealbreaker', $4, $5::jsonb)",
            USER_A,
            uuid.UUID(job["id"]),
            uuid.UUID(track),
            'Possible match for your dealbreaker "no crypto". The posting says: "x"',
            '{"role_match": "yes", "note": "Close."}',
        )
        r = await client.get(
            f"/internal/jobs/{job['id']}/screens", headers=auth(USER_A)
        )
        assert r.status_code == 200, r.text
        (row,) = r.json()
        assert row["outcome"] == "flagged"
        assert row["removedBy"] is None
        assert row["reasonCode"] == "dealbreaker"
        assert row["reason"].startswith("Possible match")
        assert row["screen"] == {"roleMatch": "yes", "note": "Close."}


async def run_sql(url: str, query: str, *args: object) -> None:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()
