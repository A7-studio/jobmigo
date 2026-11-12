"""Where each saved job stands in the person's search.

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

SCHEMA = "engine"
STAGES = "('saved', 'preparing', 'applied', 'interviewing', 'offer', 'closed')"
OUTCOMES = "('no_response', 'rejected', 'interview', 'offer')"


def upgrade() -> None:
    op.add_column(
        "job",
        sa.Column("stage", sa.Text(), nullable=False, server_default="saved"),
        schema=SCHEMA,
    )
    op.add_column("job", sa.Column("outcome", sa.Text()), schema=SCHEMA)
    op.add_column(
        "job", sa.Column("applied_at", sa.DateTime(timezone=True)), schema=SCHEMA
    )
    op.add_column("job", sa.Column("follow_up_on", sa.Date()), schema=SCHEMA)
    op.add_column(
        "job",
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        schema=SCHEMA,
    )
    op.add_column(
        "job",
        sa.Column(
            "stage_changed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_job_stage", "job", f"stage in {STAGES}", schema=SCHEMA
    )
    op.create_check_constraint(
        "ck_job_outcome",
        "job",
        f"outcome is null or outcome in {OUTCOMES}",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_job_notes", "job", "length(notes) <= 4000", schema=SCHEMA
    )


def downgrade() -> None:
    for name in ("ck_job_notes", "ck_job_outcome", "ck_job_stage"):
        op.drop_constraint(name, "job", schema=SCHEMA, type_="check")
    for column in (
        "stage_changed_at",
        "notes",
        "follow_up_on",
        "applied_at",
        "outcome",
        "stage",
    ):
        op.drop_column("job", column, schema=SCHEMA)
