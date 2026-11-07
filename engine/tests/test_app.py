import asyncio
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from engine.config import ConfigError, Settings, load_settings
from engine.jsonlog import accept_request_id
from engine.main import create_app
from engine.routes import health
from tests.conftest import TOKEN


def client(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://engine.test",
    )


async def test_healthz(app: FastAPI) -> None:
    async with client(app) as http:
        response = await http.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_request_id_is_echoed_or_generated(app: FastAPI) -> None:
    async with client(app) as http:
        echoed = await http.get("/healthz", headers={"x-request-id": "abc-123"})
        generated = await http.get("/healthz")
        hostile = await http.get("/healthz", headers={"x-request-id": "a b\tc"})
    assert echoed.headers["x-request-id"] == "abc-123"
    assert re.fullmatch(r"[0-9a-f-]{36}", generated.headers["x-request-id"])
    assert hostile.headers["x-request-id"] != "a b\tc"


async def test_unknown_route_uses_the_stable_shape(app: FastAPI) -> None:
    async with client(app) as http:
        response = await http.get("/nope")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Request failed."}


async def test_unexpected_error_is_a_stable_500(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError(f"secret detail {TOKEN}")

    caplog.set_level(logging.INFO, logger="engine")
    async with client(app) as http:
        response = await http.get("/boom")
    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Something went wrong.",
    }
    assert "x-request-id" in response.headers
    logged = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert "secret detail" not in logged
    assert TOKEN not in logged


async def test_logs_never_contain_the_token(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="engine")
    async with client(app) as http:
        await http.get("/healthz", headers={"authorization": f"Bearer {TOKEN}"})
    logged = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert "request" in logged
    assert TOKEN not in logged


def test_startup_requires_a_long_enough_token() -> None:
    base = {"DATABASE_URL": "postgresql://u:p@h/db"}
    for env in (base, {**base, "ENGINE_TOKEN": "short-secret-value"}):
        with pytest.raises(ConfigError) as caught:
            load_settings(env)
        message = str(caught.value)
        assert "ENGINE_TOKEN" in message
        assert "short-secret-value" not in message
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        load_settings({"ENGINE_TOKEN": TOKEN})


def test_create_app_fails_without_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ENGINE_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigError, match="ENGINE_TOKEN"):
        create_app()


async def test_validation_errors_use_the_stable_shape_without_echoing_input(
    app: FastAPI,
) -> None:
    @app.get("/typed")
    async def typed(n: int) -> dict[str, int]:
        return {"n": n}

    async with client(app) as http:
        response = await http.get("/typed", params={"n": "secret-value"})
    assert response.status_code == 422
    assert response.json() == {
        "code": "invalid_request",
        "message": "The request is not valid.",
    }
    assert "secret-value" not in response.text


async def test_a_wrong_method_is_a_stable_405_with_allow(app: FastAPI) -> None:
    async with client(app) as http:
        response = await http.post("/healthz")
    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"
    assert "GET" in response.headers["allow"]


async def test_readyz_needs_no_token_and_shows_no_detail(settings: Settings) -> None:
    app = create_app(
        Settings(
            engine_token=settings.engine_token,
            database_url="postgresql://x:y@127.0.0.1:1/z",
        )
    )
    async with client(app) as http:
        response = await http.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"code": "not_ready", "message": "Not ready."}
    await app.state.database.dispose()


async def test_readiness_gives_up_when_the_database_hangs(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Hanging:
        @asynccontextmanager
        async def connect(self) -> AsyncIterator[Any]:
            await asyncio.sleep(5)
            yield None

    class FakeDatabase:
        engine = Hanging()

    monkeypatch.setattr(health, "READY_TIMEOUT_SECONDS", 0.05)
    app.state.database = FakeDatabase()
    started = asyncio.get_running_loop().time()
    async with client(app) as http:
        response = await http.get("/readyz")
    assert response.status_code == 503
    assert asyncio.get_running_loop().time() - started < 2


def test_creating_the_app_opens_no_database_connection(settings: Settings) -> None:
    app = create_app(settings)
    # The engine is only built on first use, so nothing has connected.
    assert app.state.database._engine is None


def test_a_request_id_with_a_trailing_newline_is_replaced() -> None:
    for hostile in ("abc\n", "abc\r\n", "a" * 65, ""):
        assert accept_request_id(hostile) != hostile
    assert accept_request_id("abc-1.2_3") == "abc-1.2_3"


def test_a_bad_log_level_names_the_variable() -> None:
    env = {
        "ENGINE_TOKEN": TOKEN,
        "DATABASE_URL": "postgresql://u:p@h/db",
        "LOG_LEVEL": "loud",
    }
    with pytest.raises(ConfigError, match="LOG_LEVEL is not valid") as caught:
        load_settings(env)
    assert "loud" not in str(caught.value)
    assert load_settings({**env, "LOG_LEVEL": "debug"}).log_level == "DEBUG"
