"""Tracking a saved job: its stage, applied date, follow-up date, outcome and notes."""

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


async def patch(
    client: AsyncClient,
    job: dict[str, Any],
    body: dict[str, Any],
    user: uuid.UUID = USER_A,
) -> Any:
    return await client.patch(
        f"/internal/jobs/{job['id']}", headers=auth(user), json=body
    )


async def test_a_new_job_starts_saved_with_nothing_tracked(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
    assert job["stage"] == "saved"
    assert (job["outcome"], job["appliedAt"], job["followUpOn"]) == (None, None, None)
    assert job["notes"] == ""
    assert job["stageChangedAt"]


async def test_moving_to_applied_stamps_the_date_once(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        first = (await patch(client, job, {"stage": "applied"})).json()
        assert first["stage"] == "applied" and first["appliedAt"]
        second = (await patch(client, job, {"stage": "interviewing"})).json()
        assert second["stage"] == "interviewing"
        assert second["appliedAt"] == first["appliedAt"]
        assert second["stageChangedAt"] > first["stageChangedAt"]
        again = (await patch(client, job, {"stage": "applied"})).json()
        assert again["appliedAt"] == first["appliedAt"]  # never restamped


async def test_a_change_that_is_not_a_stage_change_leaves_the_stage_time_alone(
    app: FastAPI,
) -> None:
    async with http(app) as client:
        job = await add(client)
        moved = (await patch(client, job, {"stage": "preparing"})).json()
        noted = (await patch(client, job, {"notes": "Spoke to Amina."})).json()
    assert noted["stageChangedAt"] == moved["stageChangedAt"]


async def test_outcome_follow_up_and_notes_can_be_set_and_cleared(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        r = await patch(
            client,
            job,
            {
                "outcome": "no_response",
                "followUpOn": "2026-12-01",
                "notes": "Line 1\nLine 2",
            },
        )
        body = r.json()
        assert r.status_code == 200, r.text
        assert (body["outcome"], body["followUpOn"], body["notes"]) == (
            "no_response",
            "2026-12-01",
            "Line 1\nLine 2",
        )
        cleared = (
            await patch(
                client, job, {"outcome": None, "followUpOn": None, "notes": None}
            )
        ).json()
        assert (cleared["outcome"], cleared["followUpOn"], cleared["notes"]) == (
            None,
            None,
            "",
        )
        again = (await patch(client, job, {"notes": ""})).json()
        assert again["notes"] == ""


async def test_notes_keep_line_breaks_and_lose_control_characters(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        body = (await patch(client, job, {"notes": "  a\r\nb\x00\x07c\rd  "})).json()
    assert body["notes"] == "a\nbc\nd"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"stage": None},
        {"stage": "archived"},
        {"outcome": "ghosted"},
        {"followUpOn": "tomorrow"},
        {"followUpOn": "2026-13-45"},
        {"followUpOn": 5},
        {"notes": "x" * 4001},
        {"notes": 7},
        {"follow_up": "2026-12-01"},
        {"stage": "applied", "extra": 1},
    ],
)
async def test_a_bad_tracking_change_is_refused(
    app: FastAPI, body: dict[str, Any]
) -> None:
    async with http(app) as client:
        job = await add(client)
        r = await patch(client, job, body)
        assert r.status_code == 422, body
        assert set(r.json()) == {"code", "message"}
        same = (
            await client.get(f"/internal/jobs/{job['id']}", headers=auth(USER_A))
        ).json()
    assert same["stage"] == "saved" and same["notes"] == ""


async def test_tracking_a_job_needs_to_own_it(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        r = await patch(client, job, {"stage": "applied"}, user=USER_B)
        assert r.status_code == 404
        mine = (
            await client.get(f"/internal/jobs/{job['id']}", headers=auth(USER_A))
        ).json()
    assert mine["stage"] == "saved"


async def test_the_list_carries_the_tracking_fields(app: FastAPI) -> None:
    async with http(app) as client:
        job = await add(client)
        await patch(client, job, {"stage": "applied", "followUpOn": "2026-12-01"})
        listed = (await client.get("/internal/jobs", headers=auth(USER_A))).json()
    assert listed[0]["stage"] == "applied"
    assert listed[0]["followUpOn"] == "2026-12-01"
    assert "notes" in listed[0]


async def test_the_database_refuses_a_stage_or_outcome_it_does_not_know(
    app: FastAPI, db_url: str
) -> None:
    async with http(app) as client:
        await add(client)
    connection = await asyncpg.connect(db_url)
    try:
        for statement in (
            "update engine.job set stage = 'archived'",
            "update engine.job set outcome = 'ghosted'",
            "update engine.job set notes = repeat('x', 4001)",
        ):
            with pytest.raises(asyncpg.CheckViolationError):
                await connection.execute(statement)
    finally:
        await connection.close()
