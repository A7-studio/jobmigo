"""Screen one saved job against every track the user has, and keep the results.

Code gates run first and need no model. The cheap screen runs only for the tracks
that passed them. Every statement filters on the user id, and the job and the tracks
must both belong to that user. Posting text, dealbreakers and quotes are never
logged.
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from engine.ai.config import Env
from engine.ai.errors import (
    AiNotConfiguredError,
    AiOutputInvalidError,
    AiUnavailableError,
)
from engine.ai.provider import AiProvider
from engine.cv.service import not_found
from engine.db import Database
from engine.errors import ApiError
from engine.jobs import screen
from engine.jobs.gates import run_gates
from engine.jobs.service import _id
from engine.models import Job, JobScreen, Track

# How many cheap-model calls one screen may have in flight at once.
CONCURRENCY = 3

UNSCREENED = {
    AiNotConfiguredError: (
        "ai_not_configured",
        "The screen is not set up yet. The job passed the rules checked in code.",
    ),
    AiUnavailableError: (
        "ai_unavailable",
        "The screen could not be reached. Try again shortly.",
    ),
    AiOutputInvalidError: (
        "ai_invalid",
        "The screen gave an answer we could not use. Try again.",
    ),
}


class ScreenNoteOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role_match: str = Field(serialization_alias="roleMatch")
    note: str


class JobScreenOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    job_id: uuid.UUID = Field(serialization_alias="jobId")
    track_id: uuid.UUID = Field(serialization_alias="trackId")
    track_name: str = Field(serialization_alias="trackName")
    variant_version: int = Field(serialization_alias="variantVersion")
    stale: bool
    outcome: str
    removed_by: Literal["gate"] | None = Field(serialization_alias="removedBy")
    reason_code: str | None = Field(serialization_alias="reasonCode")
    reason: str | None
    screen: ScreenNoteOut | None
    updated_at: datetime = Field(serialization_alias="updatedAt")


def _out(row: JobScreen, track: Track) -> JobScreenOut:
    note = row.screen
    return JobScreenOut(
        id=row.id,
        job_id=row.job_id,
        track_id=row.track_id,
        track_name=track.name,
        variant_version=row.variant_version,
        stale=row.rules_key != rules_key(track),
        outcome=row.outcome,
        removed_by=row.removed_by,
        reason_code=row.reason_code,
        reason=row.reason,
        screen=ScreenNoteOut(role_match=note["role_match"], note=note["note"])
        if note
        else None,
        updated_at=row.updated_at,
    )


def rules_key(track: Track) -> str:
    """A fingerprint of every track rule a screen reads.

    A result is stale when this has changed since it was made. It is deliberately not
    the track's `variant_version`, which does not move when preferences are edited.
    """
    material = {
        "target_roles": list(track.target_roles),
        "work_modes": list(track.work_modes),
        "locations": list(track.locations),
        "eligibility": track.eligibility,
        "criteria": [dict(c) for c in track.criteria],
        "dealbreakers": list(track.dealbreakers),
        "do_not_apply": list(track.do_not_apply),
    }
    text = json.dumps(material, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _screen_input(job: Job, track: Track) -> screen.ScreenInput:
    return screen.ScreenInput(
        title=job.title,
        company=job.company,
        location=job.location,
        description=job.description[: screen.MAX_POSTING_CHARS],
        target_roles=list(track.target_roles),
        work_modes=list(track.work_modes),
        locations=list(track.locations),
        eligibility=track.eligibility,
        must_haves=[c["label"] for c in track.criteria if c.get("weight") == "must"],
        dealbreakers=list(track.dealbreakers),
    )


async def _owned_job(
    session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID
) -> Job:
    job = await session.scalar(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    if job is None:
        raise not_found()
    return job


async def _tracks(session: AsyncSession, user_id: uuid.UUID) -> list[Track]:
    return list(
        (
            await session.execute(
                select(Track)
                .where(Track.user_id == user_id)
                .order_by(Track.created_at, Track.id)
            )
        ).scalars()
    )


async def _decide(
    job: Job,
    track: Track,
    *,
    user_id: uuid.UUID,
    database: Database,
    gate: asyncio.Semaphore,
    env: Env | None,
    provider: AiProvider | None,
) -> dict[str, Any]:
    """The columns for one track: the gate result, else the screen result."""
    base: dict[str, Any] = {
        "user_id": user_id,
        "job_id": job.id,
        "track_id": track.id,
        "variant_version": track.variant_version,
        "rules_key": rules_key(track),
        "screen": None,
        "usage_event_id": None,
    }
    removal = run_gates(
        company=job.company,
        title=job.title,
        location=job.location,
        description=job.description,
        do_not_apply=track.do_not_apply,
        work_modes=track.work_modes,
        eligibility=track.eligibility,
        locations=track.locations,
    )
    if removal is not None:
        return {
            **base,
            "outcome": "removed",
            "removed_by": "gate",
            "reason_code": removal.code,
            "reason": removal.reason,
        }
    try:
        async with gate:
            screened = await screen.screen_posting(
                _screen_input(job, track),
                user_id=user_id,
                database=database,
                env=env,
                provider=provider,
            )
    except (AiNotConfiguredError, AiUnavailableError, AiOutputInvalidError) as error:
        code, reason = UNSCREENED[type(error)]
        return {
            **base,
            "outcome": "unscreened",
            "removed_by": None,
            "reason_code": code,
            "reason": reason,
        }
    # Each field is checked on its own: a quote never spans two of them.
    fields = [job.title, job.company, job.location, job.description]
    found = screen.flag(screened.output, track.dealbreakers, fields)
    note = {
        "role_match": screened.output.role_match,
        "note": screened.output.note,
    }
    return {
        **base,
        "screen": note,
        "usage_event_id": screened.usage_event_id,
        "outcome": "flagged" if found else "passed",
        "removed_by": None,
        "reason_code": "dealbreaker" if found else None,
        "reason": found.reason if found else None,
    }


def _is_foreign_key(error: IntegrityError) -> bool:
    """Whether the database refused a row because the job or track it names is gone."""
    code = getattr(error.orig, "sqlstate", None) or getattr(
        getattr(error.orig, "__cause__", None), "sqlstate", None
    )
    return code == "23503"


async def screen_job(
    *,
    user_id: uuid.UUID,
    job_id: str,
    database: Database,
    env: Env | None = None,
    provider: AiProvider | None = None,
) -> list[JobScreenOut]:
    """Screen a job the user owns against each of their tracks; return the results."""
    jid = _id(job_id)
    async with AsyncSession(database.engine) as session:
        job = await _owned_job(session, user_id, jid)
        tracks = await _tracks(session, user_id)
        session.expunge_all()
    if not tracks:
        raise ApiError(409, "no_tracks", "Create a track first.")

    gate = asyncio.Semaphore(CONCURRENCY)
    settled = await asyncio.gather(
        *(
            _decide(
                job,
                track,
                user_id=user_id,
                database=database,
                gate=gate,
                env=env,
                provider=provider,
            )
            for track in tracks
        ),
        return_exceptions=True,
    )
    # Every call has finished by now. Keep what worked, then report the first failure.
    rows = [item for item in settled if isinstance(item, dict)]
    failures = [item for item in settled if isinstance(item, BaseException)]

    async with AsyncSession(database.engine) as session:
        for values in rows:
            statement = insert(JobScreen).values(**values)
            # A failed re-run never erases a result: it only replaces a row that
            # was itself unscreened, or is replaced by a real result.
            upsert = statement.on_conflict_do_update(
                index_elements=["job_id", "track_id"],
                set_={
                    **{k: statement.excluded[k] for k in values},
                    "updated_at": func.now(),
                },
                where=(JobScreen.outcome == "unscreened")
                | (statement.excluded.outcome != "unscreened"),
            )
            try:
                async with session.begin_nested():
                    await session.execute(upsert)
            except IntegrityError as error:
                if not _is_foreign_key(error):
                    raise  # a bug in what we wrote is a 500, never "not found"
                # The job or this track was deleted meanwhile. Only a deleted job is
                # an error for the caller; a deleted track simply has no result.
                if (
                    await session.scalar(
                        select(Job.id).where(Job.id == jid, Job.user_id == user_id)
                    )
                    is None
                ):
                    raise not_found() from None
        await session.commit()
    if failures:
        raise failures[0]
    return await list_screens(user_id=user_id, job_id=job_id, database=database)


async def list_screens(
    *, user_id: uuid.UUID, job_id: str, database: Database
) -> list[JobScreenOut]:
    """The saved results for a job the user owns, in track order."""
    jid = _id(job_id)
    async with AsyncSession(database.engine) as session:
        await _owned_job(session, user_id, jid)
        found = (
            await session.execute(
                select(JobScreen, Track)
                .join(Track, Track.id == JobScreen.track_id)
                .where(
                    JobScreen.job_id == jid,
                    JobScreen.user_id == user_id,
                    Track.user_id == user_id,
                )
                .order_by(Track.created_at, Track.id)
            )
        ).all()
    return [_out(row, track) for row, track in found]
