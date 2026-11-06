from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import StaffContext, get_staff_context
from app.identity.dependencies import CurrentUser
from app.platform.db import get_session
from app.platform.errors import PermissionDeniedError


def require_permission(permission: str) -> Callable[..., Awaitable[StaffContext]]:
    """Dependency for staff routes: the signed-in user must be staff and hold the permission."""

    async def check(
        user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]
    ) -> StaffContext:
        staff = await get_staff_context(session, user.id)
        if staff is None or permission not in staff.permissions:
            raise PermissionDeniedError("You do not have access to this.")
        return staff

    return check
