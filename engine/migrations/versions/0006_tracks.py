"""Tracks and the facts each one emphasises.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

SCHEMA = "engine"
KINDS = "('experience', 'skill', 'achievement', 'project', 'education')"


def upgrade() -> None:
    op.create_table(
        "track",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("variant_version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.CheckConstraint("variant_version >= 1", name="ck_track_variant_version"),
        schema=SCHEMA,
    )
    op.create_index(
        "track_user_name_uniq",
        "track",
        ["user_id", sa.text("lower(name)")],
        unique=True,
        schema=SCHEMA,
    )
    op.create_table(
        "track_profile_item",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "track_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("engine.track.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(f"kind in {KINDS}", name="ck_track_profile_item_kind"),
        sa.UniqueConstraint(
            "track_id", "kind", "item_id", name="track_profile_item_uniq"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "track_profile_item_item_idx",
        "track_profile_item",
        ["user_id", "kind", "item_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("track_profile_item", schema=SCHEMA)
    op.drop_table("track", schema=SCHEMA)
