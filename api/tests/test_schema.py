import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def _make_staff(session: AsyncSession) -> str:
    user_id = await session.scalar(
        text(
            "INSERT INTO \"user\" (auth_subject, email) VALUES ('sub_1', 'a@example.com') "
            "RETURNING id"
        )
    )
    role_id = await session.scalar(text("SELECT id FROM role WHERE name = 'support'"))
    await session.execute(
        text("INSERT INTO staff_member (user_id, role_id) VALUES (:u, :r)"),
        {"u": user_id, "r": role_id},
    )
    return str(user_id)


async def test_roles_are_seeded(session: AsyncSession) -> None:
    rows = await session.execute(text("SELECT name FROM role ORDER BY name"))
    assert [r[0] for r in rows] == ["admin", "finance", "owner", "support"]
    refund = await session.scalar(
        text(
            "SELECT count(*) FROM role_permission p JOIN role r ON r.id = p.role_id "
            "WHERE r.name = 'support' AND p.permission = 'billing.refund'"
        )
    )
    assert refund == 0


async def test_user_defaults(session: AsyncSession) -> None:
    row = (
        await session.execute(
            text(
                "INSERT INTO \"user\" (auth_subject, email) VALUES ('s', 'b@example.com') "
                "RETURNING id, locale, timezone, status"
            )
        )
    ).one()
    assert (row.locale, row.timezone, row.status) == ("en", "Africa/Nairobi", "active")
    assert row.id is not None


async def test_user_status_is_constrained(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.execute(
            text("INSERT INTO \"user\" (auth_subject, email, status) VALUES ('s', 'c@e.com', 'x')")
        )


async def test_audit_log_rejects_update_and_delete(session: AsyncSession) -> None:
    staff_id = await _make_staff(session)
    audit_id = await session.scalar(
        text(
            "INSERT INTO audit_log (staff_id, action, target_type, reason) "
            "VALUES (:s, 'user.suspend', 'user', 'abuse report') RETURNING id"
        ),
        {"s": staff_id},
    )
    with pytest.raises(DBAPIError, match="append-only"):
        async with session.begin_nested():
            await session.execute(
                text("UPDATE audit_log SET reason = 'changed' WHERE id = :i"), {"i": audit_id}
            )
    with pytest.raises(DBAPIError, match="append-only"):
        async with session.begin_nested():
            await session.execute(text("DELETE FROM audit_log WHERE id = :i"), {"i": audit_id})


async def test_audit_log_requires_reason(session: AsyncSession) -> None:
    staff_id = await _make_staff(session)
    with pytest.raises(IntegrityError):
        await session.execute(
            text(
                "INSERT INTO audit_log (staff_id, action, target_type, reason) "
                "VALUES (:s, 'a', 't', '   ')"
            ),
            {"s": staff_id},
        )


_AUTH_COLUMNS = {
    "auth_user": {"id", "name", "email", "emailVerified", "image", "createdAt", "updatedAt"},
    "auth_session": {
        "id", "expiresAt", "token", "createdAt", "updatedAt", "ipAddress", "userAgent", "userId",
    },
    "auth_account": {
        "id", "accountId", "providerId", "userId", "accessToken", "refreshToken", "idToken",
        "accessTokenExpiresAt", "refreshTokenExpiresAt", "scope", "password", "createdAt",
        "updatedAt",
    },
    "auth_verification": {"id", "identifier", "value", "expiresAt", "createdAt", "updatedAt"},
    "auth_jwks": {"id", "publicKey", "privateKey", "createdAt", "expiresAt", "alg", "crv"},
}  # fmt: skip


@pytest.mark.parametrize("table", sorted(_AUTH_COLUMNS))
async def test_better_auth_tables_have_expected_columns(session: AsyncSession, table: str) -> None:
    rows = await session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
        {"t": table},
    )
    assert {r[0] for r in rows} == _AUTH_COLUMNS[table]
