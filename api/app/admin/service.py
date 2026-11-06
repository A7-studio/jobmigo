import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import StaffMember


@dataclass(frozen=True)
class StaffContext:
    user_id: uuid.UUID
    role: str
    permissions: frozenset[str]


async def get_staff_context(session: AsyncSession, user_id: uuid.UUID) -> StaffContext | None:
    member = await session.scalar(select(StaffMember).where(StaffMember.user_id == user_id))
    if member is None:
        return None
    return StaffContext(
        user_id=user_id,
        role=member.role.name,
        permissions=frozenset(p.permission for p in member.role.permissions),
    )
