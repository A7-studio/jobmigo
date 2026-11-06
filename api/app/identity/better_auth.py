import asyncio
from collections.abc import Callable
from typing import Any

import jwt

from app.identity.auth import AuthError, Identity

_LEEWAY_SECONDS = 5


class BetterAuthProvider:
    """Verifies the JWTs issued by Better Auth's jwt plugin. The only module that knows it.

    Better Auth runs in the web server and publishes its public keys at its JWKS endpoint.
    Tokens are EdDSA (Ed25519) by default; issuer and audience default to the Better Auth base URL.
    """

    def __init__(
        self,
        jwks_url: str,
        issuer: str,
        key_resolver: Callable[[str], Any] | None = None,
    ) -> None:
        self._issuer = issuer
        self._key_resolver = key_resolver or self._jwks_resolver(jwks_url)

    @staticmethod
    def _jwks_resolver(jwks_url: str) -> Callable[[str], Any]:
        client = jwt.PyJWKClient(jwks_url, cache_keys=True)
        return lambda token: client.get_signing_key_from_jwt(token).key

    async def verify(self, token: str) -> Identity:
        try:
            key = await asyncio.to_thread(self._key_resolver, token)
            claims = jwt.decode(
                token,
                key,
                algorithms=["EdDSA"],
                issuer=self._issuer,
                audience=self._issuer,
                leeway=_LEEWAY_SECONDS,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthError("Invalid session token.") from exc
        subject = claims.get("sub")
        email = claims.get("email")
        if not isinstance(subject, str) or not subject:
            raise AuthError("Token has no subject.")
        if not isinstance(email, str) or not email.strip():
            raise AuthError("Token has no email.")
        name = claims.get("name")
        return Identity(
            subject=subject,
            email=email.strip().lower(),
            display_name=name.strip() if isinstance(name, str) and name.strip() else None,
        )
