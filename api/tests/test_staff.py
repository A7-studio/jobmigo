import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import AuditReasonRequiredError, record_audit
from app.admin.dependencies import require_permission
from app.admin.service import StaffContext, get_staff_context
from app.identity.auth import get_auth_provider
from app.main import create_app
from app.platform.db import get_session
from tests.test_me import FakeAuthProvider, _bearer


@pytest.fixture
async def app(session: AsyncSession) -> AsyncIterator[FastAPI]:
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_auth_provider] = lambda: FakeAuthProvider()

    @app.get("/test/reply")
    async def reply(
        staff: StaffContext = Depends(require_permission("tickets.reply")),
    ) -> dict[str, str]:
        return {"role": staff.role}

    return app


async def _user(client: AsyncClient, subject: str) -> str:
    return str((await client.get("/v1/me", headers=_bearer(subject))).json()["id"])


async def _make_staff(session: AsyncSession, user_id: str, role: str) -> None:
    await session.execute(
        text("INSERT INTO staff_member (user_id, role_id) SELECT :u, id FROM role WHERE name = :r"),
        {"u": user_id, "r": role},
    )


async def test_non_staff_is_forbidden(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/test/reply", headers=_bearer("plain"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_wrong_role_is_forbidden_and_right_role_is_allowed(
    app: FastAPI, session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        finance = await _user(client, "fin")
        support = await _user(client, "sup")
        await _make_staff(session, finance, "finance")
        await _make_staff(session, support, "support")
        assert (await client.get("/test/reply", headers=_bearer("fin"))).status_code == 403
        allowed = await client.get("/test/reply", headers=_bearer("sup"))
    assert allowed.status_code == 200 and allowed.json() == {"role": "support"}


async def test_suspended_staff_member_is_forbidden(app: FastAPI, session: AsyncSession) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        user_id = await _user(client, "sup2")
        await _make_staff(session, user_id, "support")
        await session.execute(
            text("UPDATE \"user\" SET status = 'suspended' WHERE id = :i"), {"i": user_id}
        )
        response = await client.get("/test/reply", headers=_bearer("sup2"))
    assert response.status_code == 403


async def test_record_audit_writes_a_row_and_requires_a_reason(
    app: FastAPI, session: AsyncSession
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        user_id = await _user(client, "sup3")
    await _make_staff(session, user_id, "support")
    staff = await get_staff_context(session, uuid.UUID(user_id))
    assert staff is not None

    target = uuid.uuid4()
    entry = await record_audit(
        session,
        staff,
        "user.suspend",
        "user",
        target,
        reason="  abuse report  ",
        before={"status": "active"},
        after={"status": "suspended"},
    )
    assert entry.reason == "abuse report" and entry.target_id == target
    stored = await session.scalar(
        text("SELECT count(*) FROM audit_log WHERE action = 'user.suspend'")
    )
    assert stored == 1

    for bad in ("", "   "):
        with pytest.raises(AuditReasonRequiredError):
            await record_audit(session, staff, "x", "user", None, reason=bad)
