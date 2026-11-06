import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AuditLog
from app.admin.service import StaffContext
from app.platform.errors import DomainError


class AuditReasonRequiredError(DomainError):
    status_code = 400
    code = "reason_required"


async def record_audit(
    session: AsyncSession,
    staff: StaffContext,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    reason: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    """Append an audit row inside the caller's transaction. A reason is always required."""
    if not reason or not reason.strip():
        raise AuditReasonRequiredError("Give a reason for this action.")
    entry = AuditLog(
        staff_id=staff.user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason.strip(),
        before=before,
        after=after,
        ip=ip,
    )
    session.add(entry)
    await session.flush()
    return entry
