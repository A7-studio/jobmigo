import uuid
from typing import Any

from sqlalchemy import Delete, Select, Update, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.models import User


def owner_scoped[S: (Select[Any], Update, Delete)](statement: S, model: Any, user: User) -> S:
    """Constrain a select, update or delete to the user's own rows (tenant tables have user_id)."""
    return statement.where(model.user_id == user.id)


class OwnedRepository:
    """Base for repositories of tenant data. Every query goes through owner_scoped."""

    model: Any

    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def get(self, row_id: uuid.UUID) -> Any | None:
        statement = owner_scoped(
            select(self.model).where(self.model.id == row_id), self.model, self.user
        )
        return await self.session.scalar(statement)

    async def list_all(self) -> list[Any]:
        statement = owner_scoped(select(self.model), self.model, self.user)
        return list((await self.session.scalars(statement)).all())

    async def delete(self, row_id: uuid.UUID) -> bool:
        statement = owner_scoped(
            delete(self.model).where(self.model.id == row_id), self.model, self.user
        )
        result = await self.session.execute(statement)
        return bool(result.rowcount)  # type: ignore[attr-defined]
