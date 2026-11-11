"""A screen result can be a flag: a possible dealbreaker, not a removal.

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

SCHEMA = "engine"
CONSTRAINT = "ck_job_screen_outcome"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, "job_screen", schema=SCHEMA, type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        "job_screen",
        "outcome in ('passed', 'flagged', 'removed', 'unscreened')",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.execute(
        "update engine.job_screen set outcome = 'passed' where outcome = 'flagged'"
    )
    op.drop_constraint(CONSTRAINT, "job_screen", schema=SCHEMA, type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        "job_screen",
        "outcome in ('passed', 'removed', 'unscreened')",
        schema=SCHEMA,
    )
