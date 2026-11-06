import asyncio
import uuid
from collections.abc import AsyncIterator, Callable

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.identity.auth import AuthError, Identity, get_auth_provider
from app.identity.models import User
from app.main import create_app
from app.platform.db import get_session


class FakeAuthProvider:
    """Tokens look like 'token:<subject>'. Anything else is invalid."""

    async def verify(self, token: str) -> Identity:
        if not token.startswith("token:"):
            raise AuthError("bad token")
        subject = token.removeprefix("token:")
        return Identity(
            subject=subject, email=f"{subject}@example.com", display_name=f"Name {subject}"
        )


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _bearer(subject: str) -> dict[str, str]:
    return {"Authorization": f"Bearer token:{subject}"}


@pytest.fixture
def provider() -> FakeAuthProvider:
    return FakeAuthProvider()


@pytest.fixture
async def app(provider: FakeAuthProvider, session: AsyncSession) -> AsyncIterator[FastAPI]:
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_auth_provider] = lambda: provider
    yield app


@pytest.fixture
def unique() -> Callable[[], str]:
    return lambda: f"sub_{uuid.uuid4().hex[:10]}"


async def test_missing_header_is_401(app: FastAPI) -> None:
    async with _client(app) as client:
        assert (await client.get("/v1/me")).status_code == 401
        wrong = await client.get("/v1/me", headers={"Authorization": "Basic abc"})
        assert wrong.status_code == 401
        assert wrong.json()["error"]["code"] == "unauthorized"


async def test_invalid_token_is_401(app: FastAPI) -> None:
    async with _client(app) as client:
        response = await client.get("/v1/me", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


async def test_first_request_creates_user_and_second_reuses_it(
    app: FastAPI, provider: FakeAuthProvider, session: AsyncSession, unique: Callable[[], str]
) -> None:
    subject = unique()
    async with _client(app) as client:
        first = await client.get("/v1/me", headers=_bearer(subject))
        second = await client.get("/v1/me", headers=_bearer(subject))
    assert first.status_code == 200
    body = first.json()
    assert body["email"] == f"{subject}@example.com"
    assert body["locale"] == "en" and body["timezone"] == "Africa/Nairobi"
    assert body["staff"] is None
    assert second.json()["id"] == body["id"]
    assert "auth_subject" not in body
    count = await session.scalar(
        select(text("count(*)")).select_from(User).where(User.auth_subject == subject)
    )
    assert count == 1


async def test_suspended_user_is_403(
    app: FastAPI, session: AsyncSession, unique: Callable[[], str]
) -> None:
    subject = unique()
    async with _client(app) as client:
        await client.get("/v1/me", headers=_bearer(subject))
        await session.execute(
            text("UPDATE \"user\" SET status = 'suspended' WHERE auth_subject = :s"), {"s": subject}
        )
        response = await client.get("/v1/me", headers=_bearer(subject))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_staff_user_sees_role_and_permissions(
    app: FastAPI, session: AsyncSession, unique: Callable[[], str]
) -> None:
    subject = unique()
    async with _client(app) as client:
        user_id = (await client.get("/v1/me", headers=_bearer(subject))).json()["id"]
        await session.execute(
            text(
                "INSERT INTO staff_member (user_id, role_id) "
                "SELECT :u, id FROM role WHERE name = 'support'"
            ),
            {"u": user_id},
        )
        body = (await client.get("/v1/me", headers=_bearer(subject))).json()
    assert body["staff"]["role"] == "support"
    assert "tickets.reply" in body["staff"]["permissions"]
    assert "billing.refund" not in body["staff"]["permissions"]


async def test_concurrent_first_requests_create_one_row(
    engine: AsyncEngine, provider: FakeAuthProvider, unique: Callable[[], str]
) -> None:
    subject = unique()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(engine, expire_on_commit=False) as own:
            yield own

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_auth_provider] = lambda: provider
    try:
        async with _client(app) as client:
            responses = await asyncio.gather(
                *[client.get("/v1/me", headers=_bearer(subject)) for _ in range(4)]
            )
        assert [r.status_code for r in responses] == [200, 200, 200, 200]
        assert len({r.json()["id"] for r in responses}) == 1
        async with AsyncSession(engine) as check:
            count = await check.scalar(
                select(text("count(*)")).select_from(User).where(User.auth_subject == subject)
            )
        assert count == 1
    finally:
        async with AsyncSession(engine) as cleanup:
            await cleanup.execute(
                text('DELETE FROM "user" WHERE auth_subject = :s'), {"s": subject}
            )
            await cleanup.commit()


async def test_email_owned_by_another_identity_is_409(
    app: FastAPI, session: AsyncSession, unique: Callable[[], str]
) -> None:
    first = unique()
    await session.execute(
        text('INSERT INTO "user" (auth_subject, email) VALUES (:s, :e)'),
        {"s": "someone_else", "e": f"{first}@example.com"},
    )
    async with _client(app) as client:
        response = await client.get("/v1/me", headers=_bearer(first))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
