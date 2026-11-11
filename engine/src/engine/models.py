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
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "engine"

CV_MIMES = ("pdf", "docx")
CV_PARSE_STATUSES = ("extracted", "parsing", "parsed", "failed")
CV_PARSE_ERRORS = (
    "ai_not_configured",
    "ai_unavailable",
    "ai_output_invalid",
    "ai_input_invalid",
    "text_too_long",
    "no_profile_found",
    "interrupted",
    "internal",
)
FACT_STATUSES = ("extracted", "confirmed", "edited")

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


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return "{} in ({})".format(column, ", ".join(f"'{v}'" for v in values))


class CvFile(Base):
    """An uploaded CV: the object lives in storage, its text is kept here."""

    __tablename__ = "cv_file"
    __table_args__ = (
        CheckConstraint(_in_list("mime", CV_MIMES), name="ck_cv_file_mime"),
        CheckConstraint(
            _in_list("parse_status", CV_PARSE_STATUSES), name="ck_cv_file_parse_status"
        ),
        CheckConstraint("size_bytes >= 0", name="ck_cv_file_size"),
        CheckConstraint(
            _in_list("parse_error", CV_PARSE_ERRORS), name="ck_cv_file_parse_error"
        ),
        CheckConstraint(
            "parse_error is null or parse_status = 'failed'",
            name="ck_cv_file_parse_error_status",
        ),
        Index("cv_file_user_created_idx", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    filename: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[str] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(Text, server_default="extracted")
    parse_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def _fact_status() -> Mapped[str]:
    return mapped_column(Text, server_default="extracted")


class Profile(Base):
    """A draft of the facts parsed from one CV. Nothing in it is confirmed yet."""

    __tablename__ = "profile"
    __table_args__ = (CheckConstraint("version >= 1", name="ck_profile_version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    source_cv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("engine.cv_file.id", ondelete="CASCADE"),
        unique=True,
    )
    headline: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class _Child:
    """Columns every draft child shares."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engine.profile.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = _fact_status()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def _child_args(table: str) -> tuple[CheckConstraint, Index]:
    return (
        CheckConstraint(_in_list("status", FACT_STATUSES), name=f"ck_{table}_status"),
        Index(f"{table}_profile_position_idx", "profile_id", "position"),
    )


class Experience(_Child, Base):
    __tablename__ = "experience"
    __table_args__ = _child_args("experience")

    company: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    start: Mapped[str | None] = mapped_column(Text)
    end: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    bullets: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )


class Skill(_Child, Base):
    __tablename__ = "skill"
    __table_args__ = _child_args("skill")

    name: Mapped[str] = mapped_column(Text)


class Achievement(_Child, Base):
    __tablename__ = "achievement"
    __table_args__ = _child_args("achievement")

    text: Mapped[str] = mapped_column(Text)
    experience_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engine.experience.id", ondelete="SET NULL")
    )


class Project(_Child, Base):
    __tablename__ = "project"
    __table_args__ = _child_args("project")

    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


class Education(_Child, Base):
    __tablename__ = "education"
    __table_args__ = _child_args("education")

    institution: Mapped[str] = mapped_column(Text)
    qualification: Mapped[str | None] = mapped_column(Text)
    start: Mapped[str | None] = mapped_column(Text)
    end: Mapped[str | None] = mapped_column(Text)


class Track(Base):
    """A named job-search track; it emphasises some of the user's confirmed facts."""

    __tablename__ = "track"
    __table_args__ = (
        CheckConstraint("variant_version >= 1", name="ck_track_variant_version"),
        CheckConstraint(
            "salary_floor is null or (salary_floor >= 0 and salary_floor <= 10000000)",
            name="ck_track_salary_floor",
        ),
        CheckConstraint(
            "currency is null or currency ~ '^[A-Z]{3}$'", name="ck_track_currency"
        ),
        CheckConstraint(
            "work_modes <@ array['remote', 'hybrid', 'onsite']",
            name="ck_track_work_modes",
        ),
        Index("track_user_name_uniq", "user_id", text("lower(name)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    name: Mapped[str] = mapped_column(Text)
    variant_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    target_roles: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    salary_floor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(Text)
    work_modes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    locations: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    eligibility: Mapped[str | None] = mapped_column(Text)
    criteria: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    dealbreakers: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    do_not_apply: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TrackProfileItem(Base):
    """One fact a track emphasises. `item_id` points at one of five fact tables."""

    __tablename__ = "track_profile_item"
    __table_args__ = (
        CheckConstraint(
            "kind in ('experience', 'skill', 'achievement', 'project', 'education')",
            name="ck_track_profile_item_kind",
        ),
        UniqueConstraint("track_id", "kind", "item_id", name="track_profile_item_uniq"),
        Index("track_profile_item_item_idx", "user_id", "kind", "item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engine.track.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))


class Job(Base):
    """A job posting the user pasted in. `description` is the cleaned text."""

    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint("status in ('saved', 'dismissed')", name="ck_job_status"),
        CheckConstraint("flag in ('ok', 'review')", name="ck_job_flag"),
        Index("job_user_dedupe_uniq", "user_id", "dedupe_key", unique=True),
        Index(
            "job_user_url_uniq",
            "user_id",
            "url_key",
            unique=True,
            postgresql_where=text("url_key is not null"),
        ),
        Index("job_user_created_idx", "user_id", text("created_at desc")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    company: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    url_key: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'saved'"))
    flag: Mapped[str] = mapped_column(Text, server_default=text("'ok'"))
    findings: Mapped[dict[str, int]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class JobScreen(Base):
    """What the gates and the cheap screen decided about one job for one track."""

    __tablename__ = "job_screen"
    __table_args__ = (
        CheckConstraint(
            "outcome in ('passed', 'flagged', 'removed', 'unscreened')",
            name="ck_job_screen_outcome",
        ),
        CheckConstraint(
            "removed_by in ('gate', 'screen')", name="ck_job_screen_removed_by"
        ),
        CheckConstraint(
            "(outcome = 'removed') = (removed_by is not null)",
            name="ck_job_screen_removed",
        ),
        Index("job_screen_job_track_uniq", "job_id", "track_id", unique=True),
        Index("job_screen_user_idx", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engine.job.id", ondelete="CASCADE")
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engine.track.id", ondelete="CASCADE")
    )
    variant_version: Mapped[int] = mapped_column(Integer)
    rules_key: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    removed_by: Mapped[str | None] = mapped_column(Text)
    reason_code: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    screen: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    usage_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Evaluation(Base):
    """The evidence-based evaluation of one job for one track (replaced when re-run)."""

    __tablename__ = "evaluation"
    __table_args__ = (
        CheckConstraint(
            "band in ('strong', 'good', 'stretch', 'poor')", name="ck_evaluation_band"
        ),
        Index("evaluation_job_track_uniq", "job_id", "track_id", unique=True),
        Index("evaluation_user_idx", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engine.job.id", ondelete="CASCADE")
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engine.track.id", ondelete="CASCADE")
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engine.profile.id", ondelete="CASCADE")
    )
    profile_version: Mapped[int] = mapped_column(Integer)
    rules_key: Mapped[str] = mapped_column(Text)
    cache_key: Mapped[str] = mapped_column(Text)
    band: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    main_gap: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB)
    usage_event_ids: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
