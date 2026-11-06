from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.auth import AuthError, AuthProvider, get_auth_provider
from app.identity.models import User
from app.identity.service import get_or_create_user
from app.platform.db import get_session
from app.platform.errors import PermissionDeniedError, UnauthorizedError

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    provider: Annotated[AuthProvider, Depends(get_auth_provider)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Sign in to continue.")
    try:
        identity = await provider.verify(credentials.credentials)
    except AuthError as exc:
        raise UnauthorizedError("Your session is not valid. Sign in again.") from exc
    user = await get_or_create_user(session, identity)
    if user.status != "active":
        raise PermissionDeniedError("This account is not active.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
