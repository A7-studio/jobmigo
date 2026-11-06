from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.platform.config import get_settings
from app.platform.errors import DomainError


class AuthError(Exception):
    """The presented credentials are not valid."""


class AuthNotConfiguredError(DomainError):
    status_code = 503
    code = "unavailable"


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str
    display_name: str | None = None


class AuthProvider(Protocol):
    async def verify(self, token: str) -> Identity:
        """Return the identity for a valid token, or raise AuthError."""
        ...


@lru_cache
def _better_auth_provider() -> AuthProvider:
    from app.identity.better_auth import BetterAuthProvider

    settings = get_settings()
    if not (settings.better_auth_jwks_url and settings.better_auth_issuer):
        raise AuthNotConfiguredError("Sign-in is not configured on this server.")
    return BetterAuthProvider(
        jwks_url=settings.better_auth_jwks_url, issuer=settings.better_auth_issuer
    )


def get_auth_provider() -> AuthProvider:
    return _better_auth_provider()
