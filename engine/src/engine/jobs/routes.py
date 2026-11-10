"""The job routes. Auth is applied by the parent router."""

from fastapi import APIRouter, Request, Response

from engine.auth import CurrentUser
from engine.jobs import service
from engine.jobs.models import MAX_BODY_BYTES, JobFull, JobOut
from engine.profile.routes import _body, _database

router = APIRouter()


@router.post("", status_code=201)
async def create_job(request: Request, user_id: CurrentUser) -> JobFull:
    return await service.create_job(
        user_id=user_id,
        body=await _body(request, MAX_BODY_BYTES),
        database=_database(request),
    )


@router.get("")
async def list_jobs(
    request: Request, user_id: CurrentUser, status: str | None = None
) -> list[JobOut]:
    return await service.list_jobs(
        user_id=user_id, status=status, database=_database(request)
    )


@router.get("/{job_id}")
async def get_job(request: Request, job_id: str, user_id: CurrentUser) -> JobFull:
    return await service.get_job(
        user_id=user_id, job_id=job_id, database=_database(request)
    )


@router.patch("/{job_id}")
async def set_status(request: Request, job_id: str, user_id: CurrentUser) -> JobFull:
    return await service.set_status(
        user_id=user_id,
        job_id=job_id,
        body=await _body(request),
        database=_database(request),
    )


@router.delete("/{job_id}", status_code=204)
async def delete_job(request: Request, job_id: str, user_id: CurrentUser) -> Response:
    await service.delete_job(
        user_id=user_id, job_id=job_id, database=_database(request)
    )
    return Response(status_code=204)
