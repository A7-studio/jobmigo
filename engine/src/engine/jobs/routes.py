"""The job routes. Auth is applied by the parent router."""

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from engine.auth import CurrentUser
from engine.jobs import evaluating, kitting, screening, service
from engine.jobs.models import MAX_BODY_BYTES, FetchOut, JobFull, JobOut
from engine.profile.routes import _body, _database

router = APIRouter()


@router.post("", status_code=201)
async def create_job(request: Request, user_id: CurrentUser) -> JobFull:
    return await service.create_job(
        user_id=user_id,
        body=await _body(request, MAX_BODY_BYTES),
        database=_database(request),
    )


@router.post("/fetch")
async def fetch_page(request: Request, user_id: CurrentUser) -> FetchOut:
    return await service.fetch_job_page(
        user_id=user_id, body=await _body(request, 32 * 1024)
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


@router.post("/{job_id}/screen")
async def screen_job(
    request: Request, job_id: str, user_id: CurrentUser
) -> list[screening.JobScreenOut]:
    return await screening.screen_job(
        user_id=user_id, job_id=job_id, database=_database(request)
    )


@router.get("/{job_id}/screens")
async def list_screens(
    request: Request, job_id: str, user_id: CurrentUser
) -> list[screening.JobScreenOut]:
    return await screening.list_screens(
        user_id=user_id, job_id=job_id, database=_database(request)
    )


@router.post("/{job_id}/evaluate")
async def evaluate_job(
    request: Request, job_id: str, user_id: CurrentUser
) -> evaluating.EvaluationOut:
    return await evaluating.evaluate_job(
        user_id=user_id,
        job_id=job_id,
        body=await _body(request),
        database=_database(request),
    )


@router.get("/{job_id}/evaluations")
async def list_evaluations(
    request: Request, job_id: str, user_id: CurrentUser
) -> list[evaluating.EvaluationOut]:
    return await evaluating.list_evaluations(
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


@router.post("/{job_id}/kit")
async def write_kit(
    request: Request, job_id: str, user_id: CurrentUser
) -> list[kitting.KitVersionOut]:
    return await kitting.generate_kit(
        user_id=user_id,
        job_id=job_id,
        body=await _body(request),
        database=_database(request),
    )


@router.get("/{job_id}/kits")
async def list_kits(
    request: Request,
    job_id: str,
    user_id: CurrentUser,
    track_id: Annotated[str | None, Query(alias="trackId")] = None,
) -> list[kitting.KitVersionOut]:
    return await kitting.list_kits(
        user_id=user_id,
        job_id=job_id,
        track_id=track_id,
        database=_database(request),
    )


@router.patch("/{job_id}/kits/{kit_id}")
async def edit_kit(
    request: Request, job_id: str, kit_id: str, user_id: CurrentUser
) -> kitting.KitVersionOut:
    return await kitting.edit_kit(
        user_id=user_id,
        job_id=job_id,
        kit_id=kit_id,
        body=await _body(request),
        database=_database(request),
    )
