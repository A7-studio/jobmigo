"""Saved versions of the application kit documents.

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

SCHEMA = "engine"


def upgrade() -> None:
    op.create_table(
        "kit_version",
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
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.profile.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("doc_type", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("fact_check", postgresql.JSONB(), nullable=False),
        sa.Column(
            "usage_event_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "doc_type in ('cv', 'letter', 'proposal', 'answers')",
            name="ck_kit_version_doc_type",
        ),
        sa.CheckConstraint("version >= 1", name="ck_kit_version_version"),
        schema=SCHEMA,
    )
    op.create_index(
        "kit_version_doc_uniq",
        "kit_version",
        ["job_id", "track_id", "doc_type", "version"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index("kit_version_user_idx", "kit_version", ["user_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("kit_version", schema=SCHEMA)
