"""Internal auth: a shared bearer token plus the user id the web server vouches for.

The engine has no public port and no sessions. The web server verifies the user's
session and then calls the engine with the token and `X-User-Id`. The token is the
only thing that proves the caller is the web server, so it is compared in constant
time and is never logged or echoed.
"""

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from engine.config import Settings
from engine.errors import ApiError


def _unauthorized() -> ApiError:
    # One body for every kind of failure, so a caller learns nothing from it.
    return ApiError(401, "unauthorized", "Unauthorized.")


def require_user(request: Request) -> UUID:
    """Check the token, then return the user id the web server supplied."""
    settings: Settings = request.app.state.settings
    scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
    # Always compare, so a wrong scheme costs the same as a wrong token.
    token_ok = hmac.compare_digest(supplied.encode(), settings.engine_token.encode())
    if not (token_ok and scheme.lower() == "bearer"):
        raise _unauthorized()

    raw = request.headers.get("x-user-id", "")
    try:
        return UUID(raw)
    except ValueError:
        raise ApiError(
            400, "invalid_request", "X-User-Id must be a valid UUID."
        ) from None


CurrentUser = Annotated[UUID, Depends(require_user)]
