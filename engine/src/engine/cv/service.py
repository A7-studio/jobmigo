"""Upload, list, download and delete CVs. Every query is scoped by the user id.

Order matters on upload: validate and extract before touching storage, then store the
object, then insert the row, and remove the object again if the insert fails. Nothing
here logs a filename, key, text or URL.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.cv.extract import ExtractionError, Kind, detect_kind
from engine.cv.limits import (
    DOWNLOAD_URL_SECONDS,
    MAX_CV_BYTES,
    MAX_FILENAME_CHARS,
    MAX_LIST_ROWS,
)
from engine.db import Database
from engine.errors import ApiError
from engine.models import CvFile
from engine.storage import ObjectStore, StorageUnavailableError, clean_filename

log = logging.getLogger("engine")

Extractor = Callable[[bytes, Kind], Awaitable[str]]
MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class CvOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: uuid.UUID
    filename: str
    mime: str
    size_bytes: int = Field(alias="sizeBytes")
    parse_status: str = Field(alias="parseStatus")
    parse_error: str | None = Field(default=None, alias="parseError")
    created_at: datetime = Field(alias="createdAt")


class CvList(BaseModel):
    items: list[CvOut]


class DownloadOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: str
    expires_in_seconds: int = Field(alias="expiresInSeconds")


def too_large() -> ApiError:
    limit_mb = MAX_CV_BYTES // (1024 * 1024)
    return ApiError(
        413, "cv_too_large", f"This file is too large. The limit is {limit_mb} MB."
    )


def not_found() -> ApiError:
    return ApiError(404, "not_found", "Not found.")


def display_name(header: str | None) -> str:
    """The file name from the percent-encoded `X-Filename` header, made display-safe."""
    cleaned = clean_filename(unquote(header or ""), limit=MAX_FILENAME_CHARS)
    return cleaned or "cv"


def parse_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise not_found() from None


async def read_body(stream: AsyncIterator[bytes], declared: int | None) -> bytes:
    """The whole body, refusing as soon as it passes the limit."""
    if declared is not None and declared > MAX_CV_BYTES:
        raise too_large()
    body = bytearray()
    async for chunk in stream:
        body += chunk
        if len(body) > MAX_CV_BYTES:
            raise too_large()
    return bytes(body)


async def upload_cv(
    *,
    user_id: uuid.UUID,
    data: bytes,
    filename: str,
    database: Database,
    store: ObjectStore,
    extract: Extractor,
) -> CvOut:
    kind = detect_kind(data)
    if kind is None:
        raise ApiError(415, "cv_unsupported_type", "Upload a PDF or DOCX file.")
    try:
        text = await extract(data, kind)
    except ExtractionError as error:
        if error.reason == "unsupported":
            raise ApiError(
                415, "cv_unsupported_type", "Upload a PDF or DOCX file."
            ) from None
        raise ApiError(
            422, "cv_unreadable", "We could not read text from this file."
        ) from None

    key = f"cv/{user_id}/{uuid.uuid4()}"
    await store.put(key, data, MIME[kind])
    try:
        async with AsyncSession(database.engine, expire_on_commit=False) as session:
            row = CvFile(
                user_id=user_id,
                storage_key=key,
                filename=filename,
                mime=kind,
                size_bytes=len(data),
                extracted_text=text,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return CvOut.model_validate(row)
    except BaseException:  # includes cancellation: the object must not be orphaned
        try:
            await asyncio.shield(store.delete(key))
        except StorageUnavailableError:
            log.warning("cv cleanup failed after a failed insert")
        raise


async def list_cvs(*, user_id: uuid.UUID, database: Database) -> CvList:
    columns = (
        CvFile.id,
        CvFile.filename,
        CvFile.mime,
        CvFile.size_bytes,
        CvFile.parse_status,
        CvFile.parse_error,
        CvFile.created_at,
    )
    async with AsyncSession(database.engine) as session:
        rows = await session.execute(
            select(*columns)
            .where(CvFile.user_id == user_id)
            .order_by(CvFile.created_at.desc(), CvFile.id.desc())
            .limit(MAX_LIST_ROWS)
        )
        return CvList(
            items=[CvOut.model_validate(row, from_attributes=True) for row in rows]
        )


async def download_cv(
    *, user_id: uuid.UUID, cv_id: str, database: Database, store: ObjectStore
) -> DownloadOut:
    wanted = parse_id(cv_id)
    async with AsyncSession(database.engine) as session:
        found = (
            await session.execute(
                select(CvFile.storage_key, CvFile.filename).where(
                    CvFile.id == wanted, CvFile.user_id == user_id
                )
            )
        ).one_or_none()
    if found is None:
        raise not_found()
    url = store.signed_url(
        found.storage_key,
        expires_seconds=DOWNLOAD_URL_SECONDS,
        download_name=found.filename,
    )
    return DownloadOut(url=url, expires_in_seconds=DOWNLOAD_URL_SECONDS)


async def delete_cv(
    *, user_id: uuid.UUID, cv_id: str, database: Database, store: ObjectStore
) -> None:
    wanted = parse_id(cv_id)
    async with AsyncSession(database.engine) as session:
        key = (
            await session.execute(
                select(CvFile.storage_key).where(
                    CvFile.id == wanted, CvFile.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if key is None:
            raise not_found()
        # A storage failure raises here and the row stays, so the delete can be retried.
        await store.delete(key)
        await session.execute(
            delete(CvFile).where(CvFile.id == wanted, CvFile.user_id == user_id)
        )
        await session.commit()
