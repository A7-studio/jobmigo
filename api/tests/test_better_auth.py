import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from app.identity.auth import AuthError
from app.identity.better_auth import BetterAuthProvider

ISSUER = "http://localhost:3000"
_KEY = ed25519.Ed25519PrivateKey.generate()
_OTHER_KEY = ed25519.Ed25519PrivateKey.generate()
_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks_for(key: ed25519.Ed25519PrivateKey, kid: str = "k1") -> dict[str, Any]:
    """The shape Better Auth serves at /api/auth/jwks for an Ed25519 key."""
    jwk = jwt.PyJWK.from_dict(
        {"kty": "OKP", "crv": "Ed25519", "kid": kid, "x": _x(key)}, algorithm="EdDSA"
    )
    return {"keys": [jwk._jwk_data]}


def _x(key: ed25519.Ed25519PrivateKey) -> str:
    import base64

    from cryptography.hazmat.primitives import serialization

    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _resolver(token: str) -> Any:
    key_set = jwt.PyJWKSet.from_dict(_jwks_for(_KEY))
    kid = jwt.get_unverified_header(token)["kid"]
    return key_set[kid].key


def _token(key: Any = _KEY, alg: str = "EdDSA", **overrides: Any) -> str:
    claims: dict[str, Any] = {
        "sub": "ba_user_1",
        "email": "Sam@Example.com",
        "name": "Sam K",
        "iss": ISSUER,
        "aud": ISSUER,
        "exp": int(time.time()) + 600,
        "iat": int(time.time()),
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": "k1"})


def _provider() -> BetterAuthProvider:
    return BetterAuthProvider(
        jwks_url="http://unused.test/jwks", issuer=ISSUER, key_resolver=_resolver
    )


async def test_valid_token_returns_identity() -> None:
    identity = await _provider().verify(_token())
    assert identity.subject == "ba_user_1"
    assert identity.email == "sam@example.com"
    assert identity.display_name == "Sam K"


async def test_name_is_optional() -> None:
    identity = await _provider().verify(_token(name=None))
    assert identity.display_name is None


@pytest.mark.parametrize(
    "token",
    [
        _token(exp=int(time.time()) - 600),
        _token(iss="https://evil.test"),
        _token(aud="https://evil.test"),
        _token(key=_OTHER_KEY),
        _token(sub=None),
        _token(email=None),
        _token(email="   "),
        "not-a-token",
        "",
    ],
    ids=[
        "expired",
        "wrong-issuer",
        "wrong-audience",
        "bad-signature",
        "no-subject",
        "no-email",
        "blank-email",
        "malformed",
        "empty",
    ],
)
async def test_invalid_tokens_are_rejected(token: str) -> None:
    with pytest.raises(AuthError):
        await _provider().verify(token)


async def test_other_algorithms_are_rejected() -> None:
    hs = jwt.encode(
        {"sub": "u", "email": "a@b.c", "iss": ISSUER, "aud": ISSUER, "exp": int(time.time()) + 60},
        "x" * 32,
        "HS256",
        headers={"kid": "k1"},
    )
    rs = _token(key=_RSA_KEY, alg="RS256")
    for token in (hs, rs):
        with pytest.raises(AuthError):
            await _provider().verify(token)
