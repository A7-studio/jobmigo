"""Record whether each model call gave a usable answer.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

SCHEMA = "engine"


def upgrade() -> None:
    op.add_column(
        "usage_event",
        sa.Column("outcome", sa.Text(), nullable=False, server_default="ok"),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_usage_event_outcome",
        "usage_event",
        "outcome in ('ok', 'rejected', 'failed')",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_usage_event_outcome", "usage_event", schema=SCHEMA, type_="check"
    )
    op.drop_column("usage_event", "outcome", schema=SCHEMA)
