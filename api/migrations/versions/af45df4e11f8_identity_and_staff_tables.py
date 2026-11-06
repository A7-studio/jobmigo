"""identity and staff tables

Revision ID: af45df4e11f8
Revises:
Create Date: 2026-11-06 17:28:44.450117

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "af45df4e11f8"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Frozen copy of the staff matrix at the time of this revision.
_ALL = (
    "overview.read",
    "users.read",
    "users.write",
    "billing.read",
    "billing.refund",
    "pricing.write",
    "tickets.read",
    "tickets.reply",
    "jobs.write",
    "ai.write",
    "flags.write",
    "ops.write",
    "audit.read",
)
_ROLES = {
    "support": ("overview.read", "users.read", "tickets.read", "tickets.reply"),
    "finance": ("overview.read", "users.read", "billing.read", "billing.refund", "pricing.write"),
    "admin": tuple(p for p in _ALL if p not in ("billing.refund", "pricing.write")),
    "owner": _ALL,
}


def _seed_roles() -> None:
    conn = op.get_bind()
    for name, permissions in _ROLES.items():
        role_id = conn.execute(
            sa.text("INSERT INTO role (name) VALUES (:name) RETURNING id"), {"name": name}
        ).scalar_one()
        for permission in permissions:
            conn.execute(
                sa.text("INSERT INTO role_permission (role_id, permission) VALUES (:r, :p)"),
                {"r": role_id, "p": permission},
            )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "role",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role")),
        sa.UniqueConstraint("name", name=op.f("uq_role_name")),
    )
    op.create_table(
        "user",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("auth_subject", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("locale", sa.Text(), server_default="en", nullable=False),
        sa.Column("timezone", sa.Text(), server_default="Africa/Nairobi", nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('active', 'suspended', 'deleted')", name=op.f("ck_user_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
        sa.UniqueConstraint("auth_subject", name=op.f("uq_user_auth_subject")),
        sa.UniqueConstraint("email", name=op.f("uq_user_email")),
    )
    op.create_table(
        "role_permission",
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("permission", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.id"],
            name=op.f("fk_role_permission_role_id_role"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission", name=op.f("pk_role_permission")),
    )
    op.create_table(
        "staff_member",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("mfa_enforced", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["role.id"], name=op.f("fk_staff_member_role_id_role")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_staff_member_user_id_user"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_staff_member")),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("staff_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("length(trim(reason)) > 0", name=op.f("ck_audit_log_reason_not_empty")),
        sa.ForeignKeyConstraint(
            ["staff_id"], ["staff_member.user_id"], name=op.f("fk_audit_log_staff_id_staff_member")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )

    _seed_roles()
    op.execute(
        """
        CREATE FUNCTION audit_log_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_change
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_immutable()
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER audit_log_no_change ON audit_log")
    op.execute("DROP FUNCTION audit_log_immutable()")
    op.drop_table("audit_log")
    op.drop_table("staff_member")
    op.drop_table("role_permission")
    op.drop_table("user")
    op.drop_table("role")
