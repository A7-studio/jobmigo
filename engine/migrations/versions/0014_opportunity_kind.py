"""A job and a track each have an opportunity type: job, gig or AI training.

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

SCHEMA = "engine"
CHECK = "kind in ('job', 'gig', 'ai_training')"


def upgrade() -> None:
    for table in ("job", "track"):
        op.add_column(
            table,
            sa.Column("kind", sa.Text(), nullable=False, server_default="job"),
            schema=SCHEMA,
        )
        op.create_check_constraint(f"ck_{table}_kind", table, CHECK, schema=SCHEMA)


def downgrade() -> None:
    for table in ("track", "job"):
        op.drop_constraint(f"ck_{table}_kind", table, schema=SCHEMA, type_="check")
        op.drop_column(table, "kind", schema=SCHEMA)
