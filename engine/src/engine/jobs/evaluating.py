"""Evaluate one saved job for one track, and keep the result.

The model proposes (requirements, then a judgement of each against the user's confirmed
facts); code checks and decides (quotes, labels, importance, band, checks). A result is
saved all at once: a failure saves nothing and keeps any earlier result. Every statement
filters on the user id, and the job, the track and the profile must all belong to that
user. Posting text, facts, quotes and notes are never logged.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from engine.ai.config import Env
from engine.ai.provider import AiProvider
from engine.cv.service import not_found
from engine.db import Database
from engine.errors import ApiError
from engine.jobs import eval_band, eval_evidence, eval_extract
from engine.jobs.screening import rules_key
from engine.jobs.service import _id
from engine.models import Evaluation, Job, Track
from engine.profile.service import _validated, latest_profile


class EvaluateIn(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=False)

    track_id: uuid.UUID = Field(alias="trackId")


class EvidenceOut(BaseModel):
    kind: str
    id: uuid.UUID
    text: str


class RequirementOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    need: str
    importance: str
    quote: str
    status: str
    evidence: list[EvidenceOut]
    note: str


class MainGapOut(BaseModel):
    need: str
    status: str
    note: str


class EvaluationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    job_id: uuid.UUID = Field(serialization_alias="jobId")
    track_id: uuid.UUID = Field(serialization_alias="trackId")
    track_name: str = Field(serialization_alias="trackName")
    profile_version: int = Field(serialization_alias="profileVersion")
    stale: bool
    band: str
    summary: str
    main_gap: MainGapOut | None = Field(serialization_alias="mainGap")
    requirements: list[RequirementOut]
    checks: dict[str, Any]
    updated_at: datetime = Field(serialization_alias="updatedAt")


def _out(
    row: Evaluation, track: Track, current_profile: tuple[uuid.UUID, int] | None
) -> EvaluationOut:
    stale = (
        current_profile is None
        or current_profile != (row.profile_id, row.profile_version)
        or row.rules_key != evaluation_rules_key(track)
    )
    return EvaluationOut(
        id=row.id,
        job_id=row.job_id,
        track_id=row.track_id,
        track_name=track.name,
        profile_version=row.profile_version,
        stale=stale,
        band=row.band,
        summary=row.summary,
        main_gap=MainGapOut(**row.main_gap) if row.main_gap else None,
        requirements=[RequirementOut.model_validate(r) for r in row.requirements],
        checks=row.checks,
        updated_at=row.updated_at,
    )


def evaluation_rules_key(track: Track) -> str:
    """Every track input an evaluation reads: the screen's rules and the salary floor.

    `rules_key` alone leaves out the floor and its currency, which the salary check
    reads, so an edit to either would leave an old result looking current.
    """
    material = [rules_key(track), track.salary_floor, track.currency]
    text = json.dumps(material, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _cache_key(
    job: Job, profile_id: uuid.UUID, profile_version: int, track: Track
) -> str:
    material = {
        "job": [job.title, job.company, job.location, job.description],
        "profile": [str(profile_id), profile_version],
        "rules": evaluation_rules_key(track),
        "prompts": [eval_extract.PROMPT_VERSION, eval_evidence.PROMPT_VERSION],
    }
    text = json.dumps(material, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _is_foreign_key(error: IntegrityError) -> bool:
    code = getattr(error.orig, "sqlstate", None) or getattr(
        getattr(error.orig, "__cause__", None), "sqlstate", None
    )
    return code == "23503"


async def _owned_job(
    session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID
) -> Job:
    job = await session.scalar(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    if job is None:
        raise not_found()
    return job


async def evaluate_job(
    *,
    user_id: uuid.UUID,
    job_id: str,
    body: dict[str, object],
    database: Database,
    env: Env | None = None,
    provider: AiProvider | None = None,
) -> EvaluationOut:
    """Evaluate a job the user owns for one of their tracks, or return the kept one."""
    jid = _id(job_id)
    wanted: EvaluateIn = _validated(EvaluateIn, body)
    async with AsyncSession(database.engine) as session:
        job = await _owned_job(session, user_id, jid)
        track = await session.scalar(
            select(Track).where(Track.id == wanted.track_id, Track.user_id == user_id)
        )
        if track is None:
            raise not_found()
        profile = await latest_profile(session, user_id)
        facts = (
            await eval_evidence.load_facts(session, user_id, profile.id)
            if profile
            else []
        )
        if profile is None or not facts:
            raise ApiError(
                409, "no_confirmed_profile", "Confirm some of your profile first."
            )
        key = _cache_key(job, profile.id, profile.version, track)
        existing = await session.scalar(
            select(Evaluation).where(
                Evaluation.user_id == user_id,
                Evaluation.job_id == jid,
                Evaluation.track_id == track.id,
            )
        )
        current = (profile.id, profile.version)
        if existing is not None and existing.cache_key == key:
            return _out(existing, track, current)
        session.expunge_all()

    posting = eval_extract.ExtractInput(
        title=job.title,
        company=job.company,
        location=job.location,
        description=job.description[: eval_extract.MAX_POSTING_CHARS],
    )
    extraction = await eval_extract.extract_requirements(
        posting, user_id=user_id, database=database, env=env, provider=provider
    )
    found = extraction.extracted
    if not found.requirements:
        raise ApiError(
            422, "no_requirements", "We could not find requirements in this posting."
        )
    judging = await eval_evidence.judge(
        [(r.need, r.importance) for r in found.requirements],
        facts,
        user_id=user_id,
        database=database,
        env=env,
        provider=provider,
    )

    judged = [
        eval_band.Judged(r.need, r.importance, v.status, v.note)
        for r, v in zip(found.requirements, judging.verdicts, strict=True)
    ]
    requirements = [
        {
            "need": r.need,
            "importance": r.importance,
            "quote": r.quote,
            "status": v.status,
            "evidence": [
                {"kind": f.kind, "id": str(f.id), "text": f.text} for f in v.evidence
            ],
            "note": v.note,
        }
        for r, v in zip(found.requirements, judging.verdicts, strict=True)
    ]
    checks = {
        "salary": eval_band.salary_check(found.pay, track.salary_floor, track.currency),
        "workMode": eval_band.work_mode_check(
            job.title, job.location, job.description, list(track.work_modes)
        ),
        "region": eval_band.region_check(
            job.title,
            job.location,
            job.description,
            track.eligibility,
            list(track.locations),
        ),
    }
    values: dict[str, Any] = {
        "user_id": user_id,
        "job_id": jid,
        "track_id": track.id,
        "profile_id": profile.id,
        "profile_version": profile.version,
        "rules_key": evaluation_rules_key(track),
        "cache_key": key,
        "band": eval_band.band_for(judged),
        "summary": eval_band.summary(judged),
        "main_gap": eval_band.main_gap(judged),
        "requirements": requirements,
        "checks": checks,
        "usage_event_ids": [
            str(extraction.usage_event_id),
            str(judging.usage_event_id),
        ],
    }
    async with AsyncSession(database.engine) as session:
        statement = insert(Evaluation).values(**values)
        try:
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=["job_id", "track_id"],
                    set_={k: statement.excluded[k] for k in values}
                    | {"updated_at": func.now()},
                    # Only this user's own row is ever replaced.
                    where=Evaluation.user_id == user_id,
                )
            )
            await session.commit()
        except IntegrityError as error:
            if not _is_foreign_key(error):
                raise  # a bug in what we wrote is a 500, never "not found"
            raise not_found() from None  # the job, track or profile is gone
        row = await session.scalar(
            select(Evaluation).where(
                Evaluation.user_id == user_id,
                Evaluation.job_id == jid,
                Evaluation.track_id == track.id,
            )
        )
        if row is None:
            raise not_found()
        return _out(row, track, (profile.id, profile.version))


async def list_evaluations(
    *, user_id: uuid.UUID, job_id: str, database: Database
) -> list[EvaluationOut]:
    """The kept evaluations of a job the user owns, in track order."""
    jid = _id(job_id)
    async with AsyncSession(database.engine) as session:
        await _owned_job(session, user_id, jid)
        profile = await latest_profile(session, user_id)
        current = (profile.id, profile.version) if profile else None
        found = (
            await session.execute(
                select(Evaluation, Track)
                .join(Track, Track.id == Evaluation.track_id)
                .where(
                    Evaluation.job_id == jid,
                    Evaluation.user_id == user_id,
                    Track.user_id == user_id,
                )
                .order_by(Track.created_at, Track.id)
            )
        ).all()
        return [_out(row, track, current) for row, track in found]
