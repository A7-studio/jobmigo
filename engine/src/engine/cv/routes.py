"""The internal CV routes. Auth comes from the `/internal` router that includes this."""

from fastapi import APIRouter, Request, Response

from engine.auth import CurrentUser
from engine.cv import parse_service, service
from engine.cv.runner import run_extraction
from engine.db import Database
from engine.storage import ObjectStore, S3Store, load_storage_config

router = APIRouter()


def _database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


def _store(request: Request) -> ObjectStore:
    """The injected store (tests), else one built from the environment on first use."""
    store: ObjectStore | None = getattr(request.app.state, "object_store", None)
    if store is None:
        store = S3Store(load_storage_config())
        request.app.state.object_store = store
    return store


def _declared_length(value: str | None) -> int | None:
    """The declared size, or None when absent or not plain ASCII digits."""
    if value and value.isascii() and value.isdigit():
        return int(value)
    return None


@router.post("", status_code=201)
async def upload(request: Request, user_id: CurrentUser) -> service.CvOut:
    body = await service.read_body(
        request.stream(), _declared_length(request.headers.get("content-length"))
    )
    extract = getattr(request.app.state, "extractor", None) or run_extraction
    return await service.upload_cv(
        user_id=user_id,
        data=body,
        filename=service.display_name(request.headers.get("x-filename")),
        database=_database(request),
        store=_store(request),
        extract=extract,
    )


@router.get("")
async def list_files(request: Request, user_id: CurrentUser) -> service.CvList:
    return await service.list_cvs(user_id=user_id, database=_database(request))


@router.get("/{cv_id}")
async def status(request: Request, cv_id: str, user_id: CurrentUser) -> service.CvOut:
    return await parse_service.get_cv(
        user_id=user_id, cv_id=cv_id, database=_database(request)
    )


@router.post("/{cv_id}/parse")
async def parse(
    request: Request, response: Response, cv_id: str, user_id: CurrentUser
) -> service.CvOut:
    """Start a parse, or retry a failed one: 202 while it runs, 200 once parsed."""
    state = request.app.state
    out = await parse_service.start_parse(
        user_id=user_id,
        cv_id=cv_id,
        database=_database(request),
        jobs=state.parse_jobs,
        env=getattr(state, "ai_env", None),
        provider=getattr(state, "ai_provider", None),
    )
    response.status_code = 200 if out.parse_status == "parsed" else 202
    return out


@router.get("/{cv_id}/profile")
async def profile(
    request: Request, cv_id: str, user_id: CurrentUser
) -> parse_service.DraftOut:
    return await parse_service.get_draft(
        user_id=user_id, cv_id=cv_id, database=_database(request)
    )


@router.get("/{cv_id}/download")
async def download(
    request: Request, cv_id: str, user_id: CurrentUser
) -> service.DownloadOut:
    return await service.download_cv(
        user_id=user_id, cv_id=cv_id, database=_database(request), store=_store(request)
    )


@router.delete("/{cv_id}", status_code=204)
async def remove(request: Request, cv_id: str, user_id: CurrentUser) -> Response:
    await service.delete_cv(
        user_id=user_id, cv_id=cv_id, database=_database(request), store=_store(request)
    )
    return Response(status_code=204)
