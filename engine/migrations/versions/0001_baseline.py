"""Baseline: an empty starting point.

The `engine` schema itself is created by `migrations/env.py` so that Alembic's
version table can live in it. This revision adds nothing; feature 31 adds the first
tables as later revisions.

Revision ID: 0001
Revises:
"""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
