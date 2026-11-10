"""Profile version: changes whenever the profile or any of its facts change.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

SCHEMA = "engine"


def upgrade() -> None:
    op.add_column(
        "profile",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        schema=SCHEMA,
    )
    op.add_column(
        "profile",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_profile_version", "profile", "version >= 1", schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_constraint("ck_profile_version", "profile", schema=SCHEMA)
    op.drop_column("profile", "updated_at", schema=SCHEMA)
    op.drop_column("profile", "version", schema=SCHEMA)
