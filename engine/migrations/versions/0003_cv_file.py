"""CV files: one row per uploaded CV, with the text extracted from it.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SCHEMA = "engine"


def upgrade() -> None:
    op.create_table(
        "cv_file",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False, unique=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column(
            "parse_status", sa.Text(), nullable=False, server_default="extracted"
        ),
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
        sa.CheckConstraint("mime in ('pdf', 'docx')", name="ck_cv_file_mime"),
        sa.CheckConstraint(
            "parse_status in ('extracted', 'parsing', 'parsed', 'failed')",
            name="ck_cv_file_parse_status",
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_cv_file_size"),
        schema=SCHEMA,
    )
    op.create_index(
        "cv_file_user_created_idx",
        "cv_file",
        ["user_id", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("cv_file", schema=SCHEMA)
