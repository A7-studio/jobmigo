from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import get_staff_context
from app.identity.dependencies import CurrentUser
from app.identity.schemas import MeResponse, StaffInfo
from app.platform.db import get_session

router = APIRouter(prefix="/v1", tags=["identity"])


@router.get("/me", response_model=MeResponse)
async def me(
    user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]
) -> MeResponse:
    staff = await get_staff_context(session, user.id)
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        timezone=user.timezone,
        staff=StaffInfo(role=staff.role, permissions=sorted(staff.permissions)) if staff else None,
    )
