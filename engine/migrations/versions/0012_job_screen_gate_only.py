"""Only a code gate removes a job: old screen removals become flags.

Revision ID: 0012
Revises: 0011
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

SCHEMA = "engine"
CONSTRAINT = "ck_job_screen_removed_by"


def upgrade() -> None:
    # Rows written by the old word-matching screen stay visible, as flags the user
    # reads, not as removals. The outcome and the remover change together, so the
    # `ck_job_screen_removed` pairing holds at every row.
    op.execute(
        "update engine.job_screen set outcome = 'flagged', removed_by = null, "
        "reason_code = 'dealbreaker', "
        "reason = regexp_replace(reason, '^You ruled out ', "
        "'Possible match for your dealbreaker ') "
        "where removed_by = 'screen'"
    )
    op.drop_constraint(CONSTRAINT, "job_screen", schema=SCHEMA, type_="check")
    op.create_check_constraint(
        CONSTRAINT, "job_screen", "removed_by in ('gate')", schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "job_screen", schema=SCHEMA, type_="check")
    op.create_check_constraint(
        CONSTRAINT, "job_screen", "removed_by in ('gate', 'screen')", schema=SCHEMA
    )
