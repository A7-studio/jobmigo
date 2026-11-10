"""Jobs a user has pasted in.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

SCHEMA = "engine"


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("location", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("url_key", sa.Text()),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="saved"),
        sa.Column("flag", sa.Text(), nullable=False, server_default="ok"),
        sa.Column(
            "findings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.CheckConstraint("status in ('saved', 'dismissed')", name="ck_job_status"),
        sa.CheckConstraint("flag in ('ok', 'review')", name="ck_job_flag"),
        schema=SCHEMA,
    )
    op.create_index(
        "job_user_dedupe_uniq",
        "job",
        ["user_id", "dedupe_key"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index(
        "job_user_url_uniq",
        "job",
        ["user_id", "url_key"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("url_key is not null"),
    )
    op.create_index(
        "job_user_created_idx",
        "job",
        ["user_id", sa.text("created_at desc")],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("job", schema=SCHEMA)
