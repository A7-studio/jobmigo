"""The fetch route: it returns cleaned text, stores nothing, and passes refusals through."""

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi import FastAPI

from engine.config import Settings
from engine.errors import ApiError
from engine.jobs import fetch, service
from engine.main import create_app
from tests.conftest import TOKEN
from tests.db import upgrade
from tests.test_cv_routes import USER_A, USER_B, auth, http


@pytest.fixture
async def app(db_url: str) -> AsyncIterator[FastAPI]:
    await upgrade(db_url)
    application = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    yield application
    await application.state.database.dispose()


@pytest.fixture(autouse=True)
def fresh_limits() -> Iterator[None]:
    service._recent.clear()
    yield
    service._recent.clear()


def fake(page: fetch.Page | None = None, error: ApiError | None = None) -> Any:
    calls: list[str] = []

    async def fetcher(url: str, **_: object) -> fetch.Page:
        calls.append(url)
        if error is not None:
            raise error
        assert page is not None
        return page

    fetcher.calls = calls  # type: ignore[attr-defined]
    return fetcher


async def test_a_page_comes_back_cleaned_and_nothing_is_stored(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = fetch.Page("Build apps.", "Flutter Engineer", "https://x.example/j/1", False)
    fetcher = fake(page)
    monkeypatch.setattr(fetch, "fetch_page", fetcher)
    async with http(app) as client:
        r = await client.post(
            "/internal/jobs/fetch",
            headers=auth(),
            json={"url": "https://x.example/j/1"},
        )
        assert r.status_code == 200
        assert r.json() == {
            "text": "Build apps.",
            "title": "Flutter Engineer",
            "finalUrl": "https://x.example/j/1",
            "truncated": False,
        }
        assert fetcher.calls == ["https://x.example/j/1"]
        assert (await client.get("/internal/jobs", headers=auth())).json() == []


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (422, "validation_failed"),
        (422, "fetch_blocked"),
        (422, "robots_disallowed"),
        (422, "robots_unreadable"),
        (422, "not_a_page"),
        (422, "too_large"),
        (502, "fetch_failed"),
    ],
)
async def test_every_refusal_reaches_the_caller_with_its_code(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch, status: int, code: str
) -> None:
    monkeypatch.setattr(fetch, "fetch_page", fake(error=ApiError(status, code, "msg")))
    async with http(app) as client:
        r = await client.post(
            "/internal/jobs/fetch", headers=auth(), json={"url": "https://x.example/"}
        )
        assert (r.status_code, r.json()["code"]) == (status, code)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"url": ""},
        {"url": 5},
        {"url": "x" * 2001},
        {"url": "https://x.example/", "a": 1},
    ],
)
async def test_a_bad_body_is_a_validation_error_and_never_fetches(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]
) -> None:
    fetcher = fake(fetch.Page("t", None, "https://x.example/", False))
    monkeypatch.setattr(fetch, "fetch_page", fetcher)
    async with http(app) as client:
        r = await client.post("/internal/jobs/fetch", headers=auth(), json=body)
        assert (r.status_code, r.json()["code"]) == (422, "validation_failed")
        assert fetcher.calls == []


async def test_auth_and_the_body_cap(app: FastAPI) -> None:
    async with http(app) as client:
        assert (
            await client.post(
                "/internal/jobs/fetch", json={"url": "https://x.example/"}
            )
        ).status_code == 401
        big = await client.post(
            "/internal/jobs/fetch",
            headers=auth(),
            content=b'{"url":"' + b"x" * 40_000 + b'"}',
        )
        assert big.status_code == 422


async def test_the_eleventh_fetch_in_a_minute_is_rate_limited_per_user(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        fetch, "fetch_page", fake(fetch.Page("t", None, "https://x.example/", False))
    )
    async with http(app) as client:
        for _ in range(10):
            ok = await client.post(
                "/internal/jobs/fetch",
                headers=auth(),
                json={"url": "https://x.example/"},
            )
            assert ok.status_code == 200
        limited = await client.post(
            "/internal/jobs/fetch", headers=auth(), json={"url": "https://x.example/"}
        )
        assert (limited.status_code, limited.json()["code"]) == (429, "rate_limited")
        other = await client.post(
            "/internal/jobs/fetch",
            headers=auth(USER_B),
            json={"url": "https://x.example/"},
        )
        assert other.status_code == 200  # another user has their own allowance


def test_the_window_slides() -> None:
    for i in range(10):
        assert service._within_rate_limit(USER_A, 1000.0 + i)
    assert not service._within_rate_limit(USER_A, 1030.0)
    assert service._within_rate_limit(USER_A, 1061.0)  # the first ones have aged out


def test_the_rate_limit_table_forgets_idle_users() -> None:
    import uuid

    for _ in range(1100):
        service._within_rate_limit(uuid.uuid4(), 100.0)
    assert len(service._recent) > 1000
    service._within_rate_limit(USER_A, 500.0)  # long after: the idle ones are swept
    assert len(service._recent) <= 2
