"""Job preferences on a track.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

SCHEMA = "engine"


def _list(name: str) -> sa.Column[list[str]]:
    return sa.Column(
        name,
        postgresql.ARRAY(sa.Text()),
        nullable=False,
        server_default=sa.text("'{}'::text[]"),
    )


def upgrade() -> None:
    op.add_column("track", _list("target_roles"), schema=SCHEMA)
    op.add_column("track", sa.Column("salary_floor", sa.Integer()), schema=SCHEMA)
    op.add_column("track", sa.Column("currency", sa.Text()), schema=SCHEMA)
    op.add_column("track", _list("work_modes"), schema=SCHEMA)
    op.add_column("track", _list("locations"), schema=SCHEMA)
    op.add_column("track", sa.Column("eligibility", sa.Text()), schema=SCHEMA)
    op.add_column(
        "track",
        sa.Column(
            "criteria",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "track",
        sa.Column(
            "dealbreakers",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        schema=SCHEMA,
    )
    op.add_column("track", _list("do_not_apply"), schema=SCHEMA)
    op.create_check_constraint(
        "ck_track_salary_floor",
        "track",
        "salary_floor is null or (salary_floor >= 0 and salary_floor <= 10000000)",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_track_currency",
        "track",
        "currency is null or currency ~ '^[A-Z]{3}$'",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_track_work_modes",
        "track",
        "work_modes <@ array['remote', 'hybrid', 'onsite']",
        schema=SCHEMA,
    )


def downgrade() -> None:
    for name in ("ck_track_work_modes", "ck_track_currency", "ck_track_salary_floor"):
        op.drop_constraint(name, "track", schema=SCHEMA)
    for column in (
        "do_not_apply",
        "dealbreakers",
        "criteria",
        "eligibility",
        "locations",
        "work_modes",
        "currency",
        "salary_floor",
        "target_roles",
    ):
        op.drop_column("track", column, schema=SCHEMA)
