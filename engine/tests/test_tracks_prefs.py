"""Job preferences on a track, through the ASGI app."""

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
from tests.test_cv_routes import USER_A, USER_B, auth, http


@pytest.fixture
async def app(db_url: str) -> AsyncIterator[FastAPI]:
    await upgrade(db_url)
    application = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    yield application
    await application.state.database.dispose()


async def make(client: AsyncClient, user: uuid.UUID = USER_A) -> dict[str, Any]:
    created = await client.post(
        "/internal/tracks", headers=auth(user), json={"name": "Mobile"}
    )
    result: dict[str, Any] = created.json()
    return result


async def patch(
    client: AsyncClient,
    track: dict[str, Any],
    body: dict[str, Any],
    user: uuid.UUID = USER_A,
) -> Any:
    return await client.patch(
        f"/internal/tracks/{track['id']}/preferences", headers=auth(user), json=body
    )


EMPTY: dict[str, Any] = {
    "targetRoles": [],
    "salaryFloor": None,
    "currency": None,
    "workModes": [],
    "locations": [],
    "eligibility": None,
    "criteria": [],
    "dealbreakers": [],
    "doNotApply": [],
}


async def test_a_new_track_has_empty_preferences(app: FastAPI) -> None:
    async with http(app) as client:
        track = await make(client)
        assert track["preferences"] == EMPTY


async def test_a_change_merges_over_what_is_stored(app: FastAPI) -> None:
    async with http(app) as client:
        track = await make(client)
        first = await patch(
            client,
            track,
            {
                "targetRoles": ["Flutter  engineer", "Mobile lead"],
                "salaryFloor": 65000,
                "currency": "USD",
                "workModes": ["remote", "hybrid"],
                "locations": ["Nairobi"],
                "eligibility": "  Can work in EMEA  ",
                "criteria": [
                    {"label": "Flutter in production", "weight": "must"},
                    {"label": "Fintech", "weight": "nice"},
                ],
                "dealbreakers": ["No on-site only"],
                "doNotApply": ["Acme"],
            },
        )
        assert first.status_code == 200, first.text
        prefs = first.json()["preferences"]
        assert prefs["targetRoles"] == ["Flutter engineer", "Mobile lead"]
        assert prefs["eligibility"] == "Can work in EMEA"
        assert first.json()["variantVersion"] == 1  # criteria, not the variant

        second = await patch(client, track, {"locations": ["Nairobi", "Remote EMEA"]})
        merged = second.json()["preferences"]
        assert merged["locations"] == ["Nairobi", "Remote EMEA"]
        assert merged["salaryFloor"] == 65000  # untouched
        assert merged["criteria"][0] == {
            "label": "Flutter in production",
            "weight": "must",
        }

        cleared = await patch(client, track, {"salaryFloor": None, "currency": None})
        assert cleared.json()["preferences"]["salaryFloor"] is None
        listed = (await client.get("/internal/tracks", headers=auth())).json()
        assert listed[0]["preferences"]["locations"] == ["Nairobi", "Remote EMEA"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"unknown": 1},
        {"targetRoles": ["x"] * 11},
        {"targetRoles": ["a", "A"]},
        {"targetRoles": [""]},
        {"targetRoles": ["x" * 81]},
        {"targetRoles": "Flutter"},
        {"salaryFloor": -1, "currency": "USD"},
        {"salaryFloor": 10_000_001, "currency": "USD"},
        {"salaryFloor": "100", "currency": "USD"},
        {"salaryFloor": 1.5, "currency": "USD"},
        {"salaryFloor": 1000},  # no currency
        {"currency": "usd"},
        {"currency": "US"},
        {"workModes": ["remote", "remote"]},
        {"workModes": ["anywhere"]},
        {"eligibility": "x" * 501},
        {"criteria": [{"label": "A", "weight": "huge"}]},
        {
            "criteria": [
                {"label": "A", "weight": "must"},
                {"label": "a", "weight": "nice"},
            ]
        },
        {"criteria": [{"label": "A", "weight": "must", "extra": 1}]},
        {"criteria": [{"label": "x"}] * 31},
        {"dealbreakers": ["x" * 121]},
        {"dealbreakers": ["x"] * 11},
        {"doNotApply": ["c"] * 51},
        {"doNotApply": [5]},
    ],
)
async def test_bad_input_is_refused_and_nothing_changes(
    app: FastAPI, body: dict[str, Any]
) -> None:
    async with http(app) as client:
        track = await make(client)
        refused = await patch(client, track, body)
        assert refused.status_code == 422
        assert refused.json()["code"] == "validation_failed"
        assert "x" * 5 not in refused.text  # never echoes the input
        listed = (await client.get("/internal/tracks", headers=auth())).json()
        assert listed[0]["preferences"] == EMPTY


async def test_the_edge_bounds_are_accepted(app: FastAPI) -> None:
    async with http(app) as client:
        track = await make(client)
        ok = await patch(
            client,
            track,
            {
                "targetRoles": ["r" * 80] * 1 + [f"r{i}" for i in range(9)],
                "salaryFloor": 10_000_000,
                "currency": "KES",
                "eligibility": "e" * 500,
                "dealbreakers": ["d" * 120],
                "doNotApply": [f"c{i}" for i in range(50)],
                "criteria": [
                    {"label": f"c{i}", "weight": "important"} for i in range(30)
                ],
            },
        )
        assert ok.status_code == 200, ok.text


async def test_ownership_and_ids(app: FastAPI) -> None:
    async with http(app) as client:
        track = await make(client)
        other = await patch(client, track, {"locations": ["x"]}, USER_B)
        assert other.status_code == 404
        for bad in ("nope", str(uuid.uuid4())):
            r = await client.patch(
                f"/internal/tracks/{bad}/preferences",
                headers=auth(),
                json={"locations": ["x"]},
            )
            assert r.status_code == 404
        mine = (await client.get("/internal/tracks", headers=auth())).json()[0]
        assert mine["preferences"] == EMPTY


async def test_the_body_cap_and_auth(app: FastAPI) -> None:
    async with http(app) as client:
        track = await make(client)
        big = await client.patch(
            f"/internal/tracks/{track['id']}/preferences",
            headers=auth(),
            content=b'{"eligibility":"' + b"x" * 40000 + b'"}',
        )
        assert big.status_code == 422
        none = await client.patch(
            f"/internal/tracks/{track['id']}/preferences", json={"locations": ["x"]}
        )
        assert none.status_code == 401


async def test_the_database_refuses_bad_values_on_its_own(
    app: FastAPI, db_url: str
) -> None:
    async with http(app) as client:
        track = await make(client)
    for sql in (
        "update engine.track set currency = 'usd' where id = $1",
        "update engine.track set salary_floor = -5 where id = $1",
        "update engine.track set work_modes = array['moon'] where id = $1",
    ):
        with pytest.raises(Exception, match="violates check constraint"):
            await fetch(db_url, sql, uuid.UUID(track["id"]))
