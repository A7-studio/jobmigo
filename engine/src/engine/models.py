"""The engine's tables, all in the `engine` Postgres schema.

`user_id` columns are plain UUIDs with no foreign key: the engine never references
the web app's schema. Rows are removed by user id when account deletion arrives.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "engine"

AI_WORKFLOWS = ("parse", "screen", "evaluate", "tailor", "reach_check", "outreach")


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


class UsageEvent(Base):
    """One row per model response received, plus one per cache hit. Holds no text."""

    __tablename__ = "usage_event"
    __table_args__ = (
        CheckConstraint(
            "workflow in ({})".format(", ".join(f"'{w}'" for w in AI_WORKFLOWS)),
            name="ck_usage_event_workflow",
        ),
        CheckConstraint(
            "tokens_in >= 0 and tokens_out >= 0", name="ck_usage_event_tokens"
        ),
        Index("usage_event_user_created_idx", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    workflow: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(Integer)
    tokens_out: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    cache_hit: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AiCache(Base):
    """Validated model output, keyed per user so results are never shared."""

    __tablename__ = "ai_cache"
    __table_args__ = (PrimaryKeyConstraint("user_id", "cache_key"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    cache_key: Mapped[str] = mapped_column(Text)
    task: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    output: Mapped[Any] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
