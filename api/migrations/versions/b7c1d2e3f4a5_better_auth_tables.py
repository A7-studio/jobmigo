"""better auth tables

Revision ID: b7c1d2e3f4a5
Revises: af45df4e11f8
Create Date: 2026-11-06 18:05:00.000000

Mirrors the schema `@better-auth/cli generate` reports for the web server's
config (modelName mappings, jwt plugin). Column names are Better Auth's own
camelCase. Only the web server writes these tables.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c1d2e3f4a5"
down_revision: str | Sequence[str] | None = "af45df4e11f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE auth_user (
            "id" text NOT NULL PRIMARY KEY,
            "name" text NOT NULL,
            "email" text NOT NULL UNIQUE,
            "emailVerified" boolean NOT NULL,
            "image" text,
            "createdAt" timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE auth_session (
            "id" text NOT NULL PRIMARY KEY,
            "expiresAt" timestamptz NOT NULL,
            "token" text NOT NULL UNIQUE,
            "createdAt" timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" timestamptz NOT NULL,
            "ipAddress" text,
            "userAgent" text,
            "userId" text NOT NULL REFERENCES auth_user ("id") ON DELETE CASCADE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE auth_account (
            "id" text NOT NULL PRIMARY KEY,
            "accountId" text NOT NULL,
            "providerId" text NOT NULL,
            "userId" text NOT NULL REFERENCES auth_user ("id") ON DELETE CASCADE,
            "accessToken" text,
            "refreshToken" text,
            "idToken" text,
            "accessTokenExpiresAt" timestamptz,
            "refreshTokenExpiresAt" timestamptz,
            "scope" text,
            "password" text,
            "createdAt" timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" timestamptz NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE auth_verification (
            "id" text NOT NULL PRIMARY KEY,
            "identifier" text NOT NULL,
            "value" text NOT NULL,
            "expiresAt" timestamptz NOT NULL,
            "createdAt" timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE auth_jwks (
            "id" text NOT NULL PRIMARY KEY,
            "publicKey" text NOT NULL,
            "privateKey" text NOT NULL,
            "createdAt" timestamptz NOT NULL,
            "expiresAt" timestamptz,
            "alg" text,
            "crv" text
        )
        """
    )
    op.execute('CREATE INDEX auth_session_userId_idx ON auth_session ("userId")')
    op.execute('CREATE INDEX auth_account_userId_idx ON auth_account ("userId")')
    op.execute('CREATE INDEX auth_verification_identifier_idx ON auth_verification ("identifier")')


def downgrade() -> None:
    """Downgrade schema."""
    for table in ("auth_jwks", "auth_verification", "auth_account", "auth_session", "auth_user"):
        op.execute(f"DROP TABLE {table}")
