import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from engine.db import Database
from engine.errors import error_response

log = logging.getLogger("engine")
router = APIRouter()

READY_TIMEOUT_SECONDS = 2


class Status(BaseModel):
    status: str


@router.get("/healthz")
async def healthz() -> Status:
    """The process is up. No auth, no detail."""
    return Status(status="ok")


@router.get("/readyz", response_model=None)
async def readyz(request: Request) -> Status | JSONResponse:
    """The database answers. A failure reveals nothing about why."""
    database: Database = request.app.state.database
    try:
        async with asyncio.timeout(READY_TIMEOUT_SECONDS):
            async with database.engine.connect() as connection:
                await connection.execute(text("select 1"))
    except Exception as error:
        log.warning("not ready", extra={"error": type(error).__name__})
        return error_response(503, "not_ready", "Not ready.")
    return Status(status="ready")
