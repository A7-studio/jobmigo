from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.auth import Identity
from app.identity.models import User
from app.platform.errors import DomainError


class AccountConflictError(DomainError):
    status_code = 409
    code = "conflict"


async def get_or_create_user(session: AsyncSession, identity: Identity) -> User:
    """Find the user for a verified identity, creating the row on first sight."""
    existing = await session.scalar(select(User).where(User.auth_subject == identity.subject))
    if existing is not None:
        return existing

    statement = (
        insert(User)
        .values(
            auth_subject=identity.subject, email=identity.email, display_name=identity.display_name
        )
        .on_conflict_do_nothing()
    )
    await session.execute(statement)
    await session.commit()

    # A concurrent first request may have inserted the row. If none exists for this subject,
    # the insert was skipped because the email already belongs to another identity.
    user = await session.scalar(select(User).where(User.auth_subject == identity.subject))
    if user is None:
        raise AccountConflictError("An account with this email already exists.")
    return user
