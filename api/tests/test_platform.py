import json
import logging

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.platform.errors import UnauthorizedError
from app.platform.logging import JsonFormatter


class _Collector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(JsonFormatter().format(record))


def _app() -> FastAPI:
    app = create_app()

    @app.get("/test/unauthorized")
    async def unauthorized() -> None:
        raise UnauthorizedError("Sign in to continue.")

    @app.get("/test/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    )


async def test_unauthorized_uses_error_shape_and_request_id() -> None:
    async with _client(_app()) as client:
        response = await client.get("/test/unauthorized", headers={"X-Request-Id": "abc-123"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["x-request-id"] == "abc-123"
    assert response.json() == {"error": {"code": "unauthorized", "message": "Sign in to continue."}}


async def test_unknown_route_uses_error_shape() -> None:
    async with _client(_app()) as client:
        response = await client.get("/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.headers["x-request-id"]


async def test_unexpected_error_hides_internals() -> None:
    async with _client(_app()) as client:
        response = await client.get("/test/boom")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong."}
    }
    assert "secret" not in response.text
    assert response.headers["x-request-id"]


async def test_unsafe_incoming_request_id_is_replaced() -> None:
    async with _client(_app()) as client:
        response = await client.get("/healthz", headers={"X-Request-Id": "bad id\twith space"})
    assert response.headers["x-request-id"] != "bad id\twith space"


async def test_logs_carry_request_id_but_never_the_token() -> None:
    collector = _Collector()
    logging.getLogger("app.request").addHandler(collector)
    logging.getLogger("app.request").setLevel(logging.INFO)
    try:
        async with _client(_app()) as client:
            await client.get(
                "/healthz?email=a@example.com",
                headers={"Authorization": "Bearer SECRET-TOKEN", "X-Request-Id": "req-1"},
            )
    finally:
        logging.getLogger("app.request").removeHandler(collector)
    assert collector.lines
    entry = json.loads(collector.lines[-1])
    assert entry["path"] == "/healthz" and entry["status"] == 200
    joined = " ".join(collector.lines)
    assert "SECRET-TOKEN" not in joined and "a@example.com" not in joined
