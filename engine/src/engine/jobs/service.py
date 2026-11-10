"""Add, read, change and remove the user's pasted jobs.

Every statement filters on the user id. The pasted text is cleaned before it is stored
and is never logged or echoed in an error.
"""

import asyncio
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from engine.cv.service import not_found
from engine.db import Database
from engine.errors import ApiError
from engine.jobs import posting_guard
from engine.jobs.models import (
    MAX_DESCRIPTION_CHARS,
    MAX_JOBS,
    MIN_DESCRIPTION_CHARS,
    JobFull,
    JobIn,
    JobOut,
    StatusIn,
    dedupe_key,
    full,
    summary,
    url_key,
)
from engine.models import Job
from engine.profile.service import _validated, invalid


def _id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise not_found() from None


def _exists() -> ApiError:
    return ApiError(409, "already_exists", "You already saved that job.")


async def _owned(session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    job = (
        await session.execute(
            select(Job)
            .where(Job.id == job_id, Job.user_id == user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if job is None:
        raise not_found()
    return job


async def create_job(
    *, user_id: uuid.UUID, body: dict[str, Any], database: Database
) -> JobFull:
    parsed = _validated(JobIn, body)
    try:
        key = url_key(parsed.url)
    except ValueError:
        raise invalid() from None
    # In a worker thread; one long regex still holds the interpreter, so the cleaner
    # itself is kept linear-time and the input is capped (see posting_guard).
    text, counts = await asyncio.to_thread(posting_guard.clean_posting, parsed.text)
    if not MIN_DESCRIPTION_CHARS <= len(text) <= MAX_DESCRIPTION_CHARS:
        raise invalid()
    job = Job(
        user_id=user_id,
        company=parsed.company,
        title=parsed.title,
        location=parsed.location,
        source_url=parsed.url,
        url_key=key,
        dedupe_key=dedupe_key(parsed.company, parsed.title),
        description=text,
        flag="review" if counts.review else "ok",
        findings={
            "instructionLike": counts.instruction_like,
            "invisibleInWords": counts.invisible_in_words,
            "tagCharacters": counts.tag_characters,
            "invisibleText": counts.invisible_text,
            "mixedScriptWords": counts.mixed_script_words,
            "hiddenBlocks": counts.hidden_blocks,
            "hiddenUrls": counts.hidden_urls,
        },
    )
    async with AsyncSession(database.engine) as session:
        # One lock per user keeps two adds from both passing the cap.
        await session.execute(
            select(func.pg_advisory_xact_lock(func.hashtext(f"job:{user_id}")))
        )
        count = await session.scalar(
            select(func.count()).select_from(Job).where(Job.user_id == user_id)
        )
        if (count or 0) >= MAX_JOBS:
            raise ApiError(422, "limit_reached", "You have reached the job limit.")
        session.add(job)
        try:
            await session.commit()
        except IntegrityError:
            raise _exists() from None
        await session.refresh(job)
        return full(job)


async def list_jobs(
    *, user_id: uuid.UUID, status: str | None, database: Database
) -> list[JobOut]:
    if status not in (None, "saved", "dismissed"):
        raise invalid()
    async with AsyncSession(database.engine) as session:
        rows = (
            (
                await session.execute(
                    select(Job)
                    .where(Job.user_id == user_id, Job.status == (status or "saved"))
                    .order_by(Job.created_at.desc(), Job.id)
                )
            )
            .scalars()
            .all()
        )
        return [summary(job) for job in rows]


async def get_job(*, user_id: uuid.UUID, job_id: str, database: Database) -> JobFull:
    wanted = _id(job_id)
    async with AsyncSession(database.engine) as session:
        job = (
            await session.execute(
                select(Job).where(Job.id == wanted, Job.user_id == user_id)
            )
        ).scalar_one_or_none()
        if job is None:
            raise not_found()
        return full(job)


async def set_status(
    *, user_id: uuid.UUID, job_id: str, body: dict[str, Any], database: Database
) -> JobFull:
    wanted = _id(job_id)
    parsed = _validated(StatusIn, body)
    async with AsyncSession(database.engine) as session:
        job = await _owned(session, user_id, wanted)
        if job.status != parsed.status:
            job.status = parsed.status
            job.updated_at = func.now()
            await session.commit()
            await session.refresh(job)
        return full(job)


async def delete_job(*, user_id: uuid.UUID, job_id: str, database: Database) -> None:
    wanted = _id(job_id)
    async with AsyncSession(database.engine) as session:
        job = await _owned(session, user_id, wanted)
        await session.delete(job)
        await session.commit()
