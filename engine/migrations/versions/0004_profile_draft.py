"""Profile draft: facts parsed from a CV, and the parse failure code.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

SCHEMA = "engine"
ERRORS = (
    "ai_not_configured",
    "ai_unavailable",
    "ai_output_invalid",
    "ai_input_invalid",
    "text_too_long",
    "no_profile_found",
    "interrupted",
    "internal",
)
STATUS_CHECK = "status in ('extracted', 'confirmed', 'edited')"


def _id() -> sa.Column[object]:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _created() -> sa.Column[object]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )


def _child(name: str, *columns: sa.Column[object]) -> None:
    op.create_table(
        name,
        _id(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.profile.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        *columns,
        sa.Column("status", sa.Text(), nullable=False, server_default="extracted"),
        _created(),
        sa.CheckConstraint(STATUS_CHECK, name=f"ck_{name}_status"),
        schema=SCHEMA,
    )
    op.create_index(
        f"{name}_profile_position_idx",
        name,
        ["profile_id", "position"],
        schema=SCHEMA,
    )


def upgrade() -> None:
    op.add_column("cv_file", sa.Column("parse_error", sa.Text()), schema=SCHEMA)
    listed = ", ".join(f"'{e}'" for e in ERRORS)
    op.create_check_constraint(
        "ck_cv_file_parse_error",
        "cv_file",
        f"parse_error in ({listed})",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_cv_file_parse_error_status",
        "cv_file",
        "parse_error is null or parse_status = 'failed'",
        schema=SCHEMA,
    )

    op.create_table(
        "profile",
        _id(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_cv_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.cv_file.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("headline", sa.Text()),
        sa.Column("summary", sa.Text()),
        _created(),
        schema=SCHEMA,
    )
    _child(
        "experience",
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("start", sa.Text()),
        sa.Column("end", sa.Text()),
        sa.Column(
            "is_current", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "bullets",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    _child("skill", sa.Column("name", sa.Text(), nullable=False))
    _child(
        "achievement",
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "experience_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.experience.id", ondelete="SET NULL"),
        ),
    )
    _child(
        "project",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
    )
    _child(
        "education",
        sa.Column("institution", sa.Text(), nullable=False),
        sa.Column("qualification", sa.Text()),
        sa.Column("start", sa.Text()),
        sa.Column("end", sa.Text()),
    )


def downgrade() -> None:
    for name in ("education", "project", "achievement", "skill", "experience"):
        op.drop_table(name, schema=SCHEMA)
    op.drop_table("profile", schema=SCHEMA)
    op.drop_constraint("ck_cv_file_parse_error_status", "cv_file", schema=SCHEMA)
    op.drop_constraint("ck_cv_file_parse_error", "cv_file", schema=SCHEMA)
    op.drop_column("cv_file", "parse_error", schema=SCHEMA)
