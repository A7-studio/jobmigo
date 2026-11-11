"""The evaluation routes through the ASGI app.

No test here can reach a model: each uses an error path or a result saved in advance.
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


async def save_evaluation(
    url: str, user: uuid.UUID, job: str, track: str, profile: uuid.UUID
) -> None:
    requirements = [
        {
            "need": "Flutter",
            "importance": "must",
            "importance_source": "posting",
            "quote": "Flutter experience",
            "status": "met",
            "evidence": [{"kind": "skill", "id": str(uuid.uuid4()), "text": "Flutter"}],
            "note": "Listed.",
        }
    ]
    await run(
        url,
        "insert into engine.evaluation (user_id, job_id, track_id, profile_id, "
        "profile_version, rules_key, cache_key, band, summary, main_gap, requirements, "
        "checks) values ($1, $2, $3, $4, 1, 'r', 'c', 'strong', 'Evidence for 1 of 1 "
        "must-haves', null, $5::jsonb, $6::jsonb)",
        user,
        uuid.UUID(job),
        uuid.UUID(track),
        profile,
        json.dumps(requirements),
        json.dumps({"salary": {"status": "unknown"}}),
    )


async def test_a_saved_evaluation_is_listed_with_the_stable_shape(
    app: FastAPI, db_url: str
) -> None:
    seeded = await seed_profile(db_url, USER_A)
    async with http(app) as client:
        job = await add(client)
        track = await add_track(db_url, USER_A)
        await save_evaluation(db_url, USER_A, job["id"], track, seeded.profile_id)
        r = await client.get(
            f"/internal/jobs/{job['id']}/evaluations", headers=auth(USER_A)
        )
        assert r.status_code == 200, r.text
        rows: list[dict[str, Any]] = r.json()
        assert len(rows) == 1
        row = rows[0]
        assert set(row) == {
            "id",
            "jobId",
            "trackId",
            "trackName",
            "profileVersion",
            "stale",
            "band",
            "summary",
            "mainGap",
            "requirements",
            "checks",
            "updatedAt",
        }
        assert (row["band"], row["trackName"], row["mainGap"]) == (
            "strong",
            "Mobile",
            None,
        )
        assert set(row["requirements"][0]) == {
            "need",
            "importance",
            "importanceSource",
            "quote",
            "status",
            "evidence",
            "note",
        }
        # The saved row carries a placeholder rules key, so it cannot match the track.
        assert row["stale"] is True


async def test_a_job_with_no_evaluation_lists_none(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        r = await client.get(
            f"/internal/jobs/{job['id']}/evaluations", headers=auth(USER_A)
        )
        assert (r.status_code, r.json()) == (200, [])


async def test_a_made_up_or_foreign_job_or_track_is_not_found(
    app: FastAPI, db_url: str
) -> None:
    await seed_profile(db_url, USER_A)
    async with http(app) as client:
        theirs = await add(client, user=USER_B)
        mine = await add(client, user=USER_A)
        my_track = await add_track(db_url, USER_A)
        their_track = await add_track(db_url, USER_B, "Theirs")
        for job_id, track in (
            (str(uuid.uuid4()), my_track),
            ("nope", my_track),
            (theirs["id"], my_track),
            (mine["id"], their_track),
            (mine["id"], str(uuid.uuid4())),
        ):
            r = await client.post(
                f"/internal/jobs/{job_id}/evaluate",
                headers=auth(USER_A),
                json={"trackId": track},
            )
            assert r.status_code == 404, (job_id, track, r.text)
            assert r.json() == {"code": "not_found", "message": "Not found."}
        for job_id in (str(uuid.uuid4()), "nope", theirs["id"]):
            r = await client.get(
                f"/internal/jobs/{job_id}/evaluations", headers=auth(USER_A)
            )
            assert r.status_code == 404


@pytest.mark.parametrize("bad", [{}, {"trackId": "nope"}, {"trackId": 3}, {"x": 1}])
async def test_a_missing_or_malformed_track_id_is_refused(
    app: FastAPI, bad: dict[str, Any]
) -> None:
    async with http(app) as client:
        job = await add(client)
        r = await client.post(
            f"/internal/jobs/{job['id']}/evaluate", headers=auth(USER_A), json=bad
        )
        assert r.status_code == 422
        assert r.json()["code"] == "validation_failed"


async def test_a_user_with_no_confirmed_facts_is_asked_to_confirm(
    app: FastAPI, db_url: str
) -> None:
    await seed_profile(db_url, USER_A)  # everything is still `extracted`
    async with http(app) as client:
        job = await add(client)
        track = await add_track(db_url, USER_A)
        r = await client.post(
            f"/internal/jobs/{job['id']}/evaluate",
            headers=auth(USER_A),
            json={"trackId": track},
        )
        assert r.status_code == 409
        assert r.json() == {
            "code": "no_confirmed_profile",
            "message": "Confirm some of your profile first.",
        }


async def test_the_routes_need_the_engine_token(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        post = await client.post(
            f"/internal/jobs/{job['id']}/evaluate", json={"trackId": str(uuid.uuid4())}
        )
        get = await client.get(f"/internal/jobs/{job['id']}/evaluations")
        assert post.status_code in (401, 403)
        assert get.status_code in (401, 403)
