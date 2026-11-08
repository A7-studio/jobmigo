"""The AI usage ledger and per-user cache (moved here from the web schema).

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SCHEMA = "engine"
WORKFLOWS = ("parse", "screen", "evaluate", "tailor", "reach_check", "outreach")


def upgrade() -> None:
    op.create_table(
        "usage_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "workflow in ({})".format(", ".join(f"'{w}'" for w in WORKFLOWS)),
            name="ck_usage_event_workflow",
        ),
        sa.CheckConstraint(
            "tokens_in >= 0 and tokens_out >= 0", name="ck_usage_event_tokens"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "usage_event_user_created_idx",
        "usage_event",
        ["user_id", "created_at"],
        schema=SCHEMA,
    )
    op.create_table(
        "ai_cache",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("output", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("user_id", "cache_key"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("ai_cache", schema=SCHEMA)
    op.drop_index(
        "usage_event_user_created_idx", table_name="usage_event", schema=SCHEMA
    )
    op.drop_table("usage_event", schema=SCHEMA)
