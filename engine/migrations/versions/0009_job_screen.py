"""What the gates and the cheap screen decided about a job, per track.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

SCHEMA = "engine"


def upgrade() -> None:
    op.create_table(
        "job_screen",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.job.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "track_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.track.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant_version", sa.Integer(), nullable=False),
        sa.Column("rules_key", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("removed_by", sa.Text()),
        sa.Column("reason_code", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column("screen", postgresql.JSONB()),
        sa.Column("usage_event_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "outcome in ('passed', 'removed', 'unscreened')",
            name="ck_job_screen_outcome",
        ),
        sa.CheckConstraint(
            "removed_by in ('gate', 'screen')", name="ck_job_screen_removed_by"
        ),
        sa.CheckConstraint(
            "(outcome = 'removed') = (removed_by is not null)",
            name="ck_job_screen_removed",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "job_screen_job_track_uniq",
        "job_screen",
        ["job_id", "track_id"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index("job_screen_user_idx", "job_screen", ["user_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("job_screen", schema=SCHEMA)
