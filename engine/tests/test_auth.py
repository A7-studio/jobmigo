import hmac
import logging
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from engine.main import create_app
from tests.conftest import TOKEN

USER = str(uuid.uuid4())


def client(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://engine.test",
    )


def headers(
    token: str = TOKEN, user: str | None = USER, scheme: str = "Bearer"
) -> dict[str, str]:
    result = {"authorization": f"{scheme} {token}"}
    if user is not None:
        result["x-user-id"] = user
    return result


async def test_valid_call_returns_the_user_id(app: FastAPI) -> None:
    async with client(app) as http:
        response = await http.get("/internal/whoami", headers=headers())
    assert response.status_code == 200
    assert response.json() == {"userId": USER}


async def test_every_kind_of_bad_token_gets_the_same_401(app: FastAPI) -> None:
    attempts = [
        {},
        {"x-user-id": USER},
        headers(token="wrong" * 8),
        headers(token="short"),
        headers(token=TOKEN + "extra"),
        headers(scheme="Basic"),
        {"authorization": TOKEN, "x-user-id": USER},
        {"authorization": "Bearer", "x-user-id": USER},
    ]
    bodies = set()
    async with client(app) as http:
        for attempt in attempts:
            response = await http.get("/internal/whoami", headers=attempt)
            assert response.status_code == 401
            bodies.add(response.text)
    assert len(bodies) == 1
    assert TOKEN not in bodies.pop()


@pytest.mark.parametrize("user", [None, "", "not-a-uuid", "123", USER + "0"])
async def test_a_bad_user_id_is_a_400(app: FastAPI, user: str | None) -> None:
    async with client(app) as http:
        response = await http.get("/internal/whoami", headers=headers(user=user))
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


async def test_the_token_is_checked_before_the_user_id(app: FastAPI) -> None:
    async with client(app) as http:
        response = await http.get(
            "/internal/whoami", headers=headers(token="x" * 40, user="bad")
        )
    assert response.status_code == 401


async def test_health_routes_need_no_token(app: FastAPI) -> None:
    async with client(app) as http:
        assert (await http.get("/healthz")).status_code == 200


async def test_the_token_is_always_compared_in_constant_time(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    real = hmac.compare_digest

    def spy(a: bytes, b: bytes) -> bool:
        calls.append(len(a))
        return bool(real(a, b))

    monkeypatch.setattr(hmac, "compare_digest", spy)
    async with client(app) as http:
        for attempt in ({}, headers(token="nope"), headers(scheme="Basic"), headers()):
            await http.get("/internal/whoami", headers=attempt)
    # Even a missing header or a wrong scheme goes through the same comparison.
    assert len(calls) == 4


async def test_every_internal_route_requires_the_token(app: FastAPI) -> None:
    paths = {
        path: list(methods)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith("/internal")
    }
    assert paths, "expected at least one internal route"
    async with client(app) as http:
        for path, methods in paths.items():
            for method in methods:
                response = await http.request(method.upper(), path)
                assert response.status_code == 401, f"{method} {path}"


async def test_a_route_added_to_the_internal_router_is_protected(app: FastAPI) -> None:
    from engine.routes import internal

    @internal.router.get("/probe-test-only")
    async def probe() -> dict[str, bool]:
        return {"ok": True}

    # Routes registered after the app was built are not served, so build a fresh app.
    fresh = create_app(app.state.settings)
    async with client(fresh) as http:
        response = await http.get("/internal/probe-test-only")
    internal.router.routes[:] = [
        r
        for r in internal.router.routes
        if getattr(r, "path", "") != "/internal/probe-test-only"
    ]
    assert response.status_code == 401


async def test_the_token_never_appears_in_logs_or_responses(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="engine")
    async with client(app) as http:
        ok = await http.get("/internal/whoami", headers=headers())
        bad = await http.get("/internal/whoami", headers=headers(token="y" * 40))
    logged = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    for secret in (TOKEN, "y" * 40, USER):
        assert secret not in logged
    assert TOKEN not in ok.text + bad.text
