"""Routes only the web server may call."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from engine.auth import CurrentUser, require_user
from engine.cv import routes as cv_routes

# Auth is required by the router itself, so a route added here later cannot forget it.
router = APIRouter(prefix="/internal", dependencies=[Depends(require_user)])

router.include_router(cv_routes.router, prefix="/cv")


class WhoAmI(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias="userId")


@router.get("/whoami")
async def whoami(user_id: CurrentUser) -> WhoAmI:
    """Prove the boundary: echo the user id the caller vouched for."""
    return WhoAmI(user_id=user_id)
