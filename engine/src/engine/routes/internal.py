"""Routes only the web server may call."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from engine.ai.usage_report import UsageReport, usage_report
from engine.auth import CurrentUser, require_user
from engine.cv import routes as cv_routes
from engine.jobs import routes as job_routes
from engine.profile import routes as profile_routes
from engine.tracks import routes as track_routes

# Auth is required by the router itself, so a route added here later cannot forget it.
router = APIRouter(prefix="/internal", dependencies=[Depends(require_user)])

router.include_router(cv_routes.router, prefix="/cv")
router.include_router(profile_routes.router, prefix="/profile")
router.include_router(track_routes.router, prefix="/tracks")
router.include_router(job_routes.router, prefix="/jobs")


class WhoAmI(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias="userId")


@router.get("/whoami")
async def whoami(user_id: CurrentUser) -> WhoAmI:
    """Prove the boundary: echo the user id the caller vouched for."""
    return WhoAmI(user_id=user_id)


@router.get("/admin/ai-usage")
async def ai_usage(request: Request, days: int = 30) -> UsageReport:
    """Aggregates over every user's ledger rows. The web server checks staff access."""
    return await usage_report(request.app.state.database, days=days)
