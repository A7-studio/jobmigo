"""Write the application kit for one saved job and one track, and keep every version.

A kit is a CV, a cover letter (job) or a proposal (gig or AI training role), and
answers to application questions when some are given. Each is its own model call,
written from the user's confirmed or edited facts only (`kit_write`), then checked by
code (`kit_check`). A kit is saved all at once: if any document fails, none is saved and
earlier versions stay. The same inputs again return the latest version with no model
call. Every statement filters on the user id. Posting text, facts, questions and
documents are never logged.
"""

import asyncio
import base64
import hashlib
import json
import uuid
import weakref
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.ai.config import Env
from engine.ai.provider import AiProvider
from engine.cv.parse import _clean
from engine.cv.service import not_found
from engine.db import Database
from engine.errors import ApiError
from engine.jobs import kit_edit, kit_export, kit_write
from engine.jobs.eval_evidence import Fact, load_facts
from engine.jobs.kit_write import MAX_QUESTION_CHARS, MAX_QUESTIONS, PostingIn, Written
from engine.jobs.service import _id
from engine.models import Job, KitVersion, Track
from engine.profile.service import _validated, latest_profile
from engine.storage import clean_filename

MAX_VERSIONS = 10
DOC_ORDER = ("cv", "letter", "proposal", "answers")


def _question(value: object) -> object:
    return _clean(value) if isinstance(value, str) else value


def _questions(value: object) -> object:
    """Blank questions are dropped; the rest are cleaned."""
    if not isinstance(value, list):
        return value
    cleaned = [_question(v) for v in value]
    return [v for v in cleaned if v != ""]


class KitIn(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=False)

    track_id: uuid.UUID = Field(alias="trackId")
    questions: Annotated[
        list[Annotated[str, Field(max_length=MAX_QUESTION_CHARS)]],
        BeforeValidator(_questions),
        Field(max_length=MAX_QUESTIONS),
    ] = Field(default_factory=list)


class KitVersionOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    job_id: uuid.UUID = Field(serialization_alias="jobId")
    track_id: uuid.UUID = Field(serialization_alias="trackId")
    track_name: str = Field(serialization_alias="trackName")
    doc_type: str = Field(serialization_alias="docType")
    version: int
    profile_version: int = Field(serialization_alias="profileVersion")
    stale: bool
    content: dict[str, Any]
    fact_check: dict[str, Any] = Field(serialization_alias="factCheck")
    created_at: datetime = Field(serialization_alias="createdAt")


def _out(
    row: KitVersion, track: Track, current: tuple[uuid.UUID, int] | None
) -> KitVersionOut:
    return KitVersionOut(
        id=row.id,
        job_id=row.job_id,
        track_id=row.track_id,
        track_name=track.name,
        doc_type=row.doc_type,
        version=row.version,
        profile_version=row.profile_version,
        stale=current != (row.profile_id, row.profile_version),
        content=row.content,
        fact_check=row.fact_check,
        created_at=row.created_at,
    )


def wanted_docs(job: Job, questions: list[str]) -> list[str]:
    """The documents a kit holds for this job: a letter for a job, else a proposal."""
    docs = ["cv", "letter" if job.kind == "job" else "proposal"]
    if questions:
        docs.append("answers")
    return docs


_PROMPTS = {
    "cv": kit_write.CV_VERSION,
    "letter": kit_write.LETTER_VERSION,
    "proposal": kit_write.PROPOSAL_VERSION,
    "answers": kit_write.ANSWERS_VERSION,
}


def _facts_hash(facts: list[Fact]) -> str:
    text = json.dumps([[f.label, f.kind, f.text] for f in facts], ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _cache_key(
    doc: str,
    job: Job,
    profile_id: uuid.UUID,
    profile_version: int,
    facts: list[Fact],
    questions: list[str],
) -> str:
    material = {
        "doc": doc,
        "job": [job.title, job.company, job.location, job.description],
        "profile": [str(profile_id), profile_version],
        "facts": _facts_hash(facts),
        "questions": questions if doc == "answers" else [],
        "prompt": _PROMPTS[doc],
    }
    text = json.dumps(material, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()[:32]


async def _owned_job(
    session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID
) -> Job:
    job = await session.scalar(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    if job is None:
        raise not_found()
    return job


async def _latest(
    session: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    track_id: uuid.UUID,
    doc: str,
) -> KitVersion | None:
    return await session.scalar(
        select(KitVersion)
        .where(
            KitVersion.user_id == user_id,
            KitVersion.job_id == job_id,
            KitVersion.track_id == track_id,
            KitVersion.doc_type == doc,
        )
        .order_by(KitVersion.version.desc())
        .limit(1)
    )


async def _write(
    doc: str,
    posting: PostingIn,
    facts: list[Fact],
    questions: list[str],
    *,
    user_id: uuid.UUID,
    database: Database,
    env: Env | None,
    provider: AiProvider | None,
) -> Written:
    task_input = kit_write.kit_input(
        posting, facts, questions if doc == "answers" else []
    )
    common: dict[str, Any] = {
        "user_id": user_id,
        "database": database,
        "env": env,
        "provider": provider,
    }
    if doc == "cv":
        return await kit_write.write_cv(task_input, facts, **common)
    if doc == "answers":
        return await kit_write.write_answers(task_input, facts, **common)
    return await kit_write.write_paragraphs(
        "letter" if doc == "letter" else "proposal", task_input, facts, **common
    )


# One request at a time per user, job and track in this process, so identical requests
# made together wait, then find the saved kit instead of each paying for a model call.
_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()


def _lock_for(
    user_id: uuid.UUID, job_id: uuid.UUID, track_id: uuid.UUID
) -> asyncio.Lock:
    key = f"{user_id}:{job_id}:{track_id}"
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


async def generate_kit(
    *,
    user_id: uuid.UUID,
    job_id: str,
    body: dict[str, object],
    database: Database,
    env: Env | None = None,
    provider: AiProvider | None = None,
) -> list[KitVersionOut]:
    """Write the kit for a job the user owns, or return the kept versions."""
    jid = _id(job_id)
    wanted: KitIn = _validated(KitIn, body)
    async with _lock_for(user_id, jid, wanted.track_id):
        return await _generate(
            user_id, jid, wanted, database=database, env=env, provider=provider
        )


async def _generate(
    user_id: uuid.UUID,
    jid: uuid.UUID,
    wanted: KitIn,
    *,
    database: Database,
    env: Env | None,
    provider: AiProvider | None,
) -> list[KitVersionOut]:
    async with AsyncSession(database.engine) as session:
        job = await _owned_job(session, user_id, jid)
        track = await session.scalar(
            select(Track).where(Track.id == wanted.track_id, Track.user_id == user_id)
        )
        if track is None:
            raise not_found()
        if track.kind != job.kind:
            raise ApiError(
                422, "wrong_type", "That track is for a different type of opportunity."
            )
        profile = await latest_profile(session, user_id)
        facts = await load_facts(session, user_id, profile.id) if profile else []
        if profile is None or not facts:
            raise ApiError(
                409, "no_confirmed_profile", "Confirm some of your profile first."
            )
        docs = wanted_docs(job, wanted.questions)
        keys = {
            doc: _cache_key(
                doc, job, profile.id, profile.version, facts, wanted.questions
            )
            for doc in docs
        }
        current = (profile.id, profile.version)
        kept: dict[str, KitVersion] = {}
        for doc in docs:
            latest = await _latest(session, user_id, jid, track.id, doc)
            if latest is not None and latest.cache_key == keys[doc]:
                kept[doc] = latest
        if len(kept) == len(docs):
            return [_out(kept[doc], track, current) for doc in docs]
        posting = PostingIn(
            company=job.company,
            title=job.title,
            location=job.location,
            description=job.description,
        )
        profile_id, profile_version = profile.id, profile.version
        track_id = track.id
        session.expunge_all()

    written: dict[str, Written] = {}
    for doc in docs:
        if doc in kept:
            continue
        written[doc] = await _write(
            doc,
            posting,
            facts,
            wanted.questions,
            user_id=user_id,
            database=database,
            env=env,
            provider=provider,
        )

    async with AsyncSession(database.engine) as session:
        # One lock per job and track keeps two saves from taking one version number.
        await session.execute(
            select(func.pg_advisory_xact_lock(func.hashtext(f"kit:{jid}:{track_id}")))
        )
        saved: dict[str, KitVersion] = {}
        for doc, result in written.items():
            # Another engine process may have saved this exact kit while we wrote it.
            existing = await _latest(session, user_id, jid, track_id, doc)
            if existing is not None and existing.cache_key == keys[doc]:
                kept[doc] = existing
                continue
            top = await session.scalar(
                select(func.max(KitVersion.version)).where(
                    KitVersion.user_id == user_id,
                    KitVersion.job_id == jid,
                    KitVersion.track_id == track_id,
                    KitVersion.doc_type == doc,
                )
            )
            row = KitVersion(
                user_id=user_id,
                job_id=jid,
                track_id=track_id,
                profile_id=profile_id,
                profile_version=profile_version,
                doc_type=doc,
                version=(top or 0) + 1,
                cache_key=keys[doc],
                content=result.content,
                fact_check=result.fact_check,
                usage_event_ids=[str(result.usage_event_id)],
            )
            session.add(row)
            saved[doc] = row
            # Keep the newest MAX_VERSIONS; older ones are deleted.
            await session.execute(
                delete(KitVersion).where(
                    KitVersion.user_id == user_id,
                    KitVersion.job_id == jid,
                    KitVersion.track_id == track_id,
                    KitVersion.doc_type == doc,
                    KitVersion.version <= row.version - MAX_VERSIONS,
                )
            )
        await session.commit()
        track_row = await session.scalar(
            select(Track).where(Track.id == track_id, Track.user_id == user_id)
        )
        if track_row is None:
            raise not_found()
        for row in saved.values():
            await session.refresh(row)
        merged = {**kept, **saved}
        return [
            _out(merged[doc], track_row, (profile_id, profile_version)) for doc in docs
        ]


async def list_kits(
    *,
    user_id: uuid.UUID,
    job_id: str,
    track_id: str | None,
    database: Database,
) -> list[KitVersionOut]:
    """Kept versions of a job the user owns, newest first.

    Without a track: the latest version of each document for each track of the job's
    type. With a track: every kept version for that track. Results for tracks of another
    type are hidden, as for screens and evaluations.
    """
    jid = _id(job_id)
    wanted_track = _id(track_id) if track_id is not None else None
    async with AsyncSession(database.engine) as session:
        job = await _owned_job(session, user_id, jid)
        profile = await latest_profile(session, user_id)
        current = (profile.id, profile.version) if profile else None
        statement = (
            select(KitVersion, Track)
            .join(Track, Track.id == KitVersion.track_id)
            .where(
                KitVersion.job_id == jid,
                KitVersion.user_id == user_id,
                Track.user_id == user_id,
                Track.kind == job.kind,
            )
            .order_by(
                Track.created_at,
                Track.id,
                KitVersion.doc_type,
                KitVersion.version.desc(),
            )
        )
        if wanted_track is not None:
            statement = statement.where(KitVersion.track_id == wanted_track)
        found = (await session.execute(statement)).all()
    if wanted_track is not None:
        return [_out(row, track, current) for row, track in found]
    latest: dict[tuple[uuid.UUID, str], tuple[KitVersion, Track]] = {}
    for row, track in found:
        latest.setdefault((row.track_id, row.doc_type), (row, track))
    ordered = sorted(
        latest.values(),
        key=lambda pair: (
            pair[1].created_at,
            str(pair[1].id),
            DOC_ORDER.index(pair[0].doc_type),
        ),
    )
    return [_out(row, track, current) for row, track in ordered]


class EditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=kit_edit.MAX_PATH_CHARS)
    action: Literal["edit", "remove"]
    text: str | None = Field(default=None, max_length=kit_edit.MAX_EDIT_CHARS)


async def edit_kit(
    *,
    user_id: uuid.UUID,
    job_id: str,
    kit_id: str,
    body: dict[str, object],
    database: Database,
) -> KitVersionOut:
    """Edit or remove one statement of the latest version, saved as a new version."""
    jid = _id(job_id)
    kid = _id(kit_id)
    wanted: EditIn = _validated(EditIn, body)
    async with AsyncSession(database.engine) as session:
        job = await _owned_job(session, user_id, jid)
        shown = await session.scalar(
            select(KitVersion).where(
                KitVersion.id == kid,
                KitVersion.user_id == user_id,
                KitVersion.job_id == jid,
            )
        )
        track = (
            await session.scalar(
                select(Track).where(
                    Track.id == shown.track_id, Track.user_id == user_id
                )
            )
            if shown is not None
            else None
        )
        if shown is None or track is None or track.kind != job.kind:
            raise not_found()
        track_id, doc = shown.track_id, shown.doc_type
    async with (
        _lock_for(user_id, jid, track_id),
        AsyncSession(database.engine) as session,
    ):
        await session.execute(
            select(func.pg_advisory_xact_lock(func.hashtext(f"kit:{jid}:{track_id}")))
        )
        latest = await _latest(session, user_id, jid, track_id, doc)
        if latest is None:
            raise not_found()
        if latest.id != kid:
            raise ApiError(
                409, "not_latest", "A newer version exists. Reload this page."
            )
        facts = await load_facts(session, user_id, latest.profile_id)
        changed = kit_edit.apply_edit(
            latest.content, wanted.path, wanted.action, wanted.text
        )
        content, check = kit_edit.recheck(
            changed, facts, int(latest.fact_check.get("omitted", 0))
        )
        material = f"{latest.cache_key}|{wanted.path}|{wanted.action}|{wanted.text}"
        row = KitVersion(
            user_id=user_id,
            job_id=jid,
            track_id=track_id,
            profile_id=latest.profile_id,
            profile_version=latest.profile_version,
            doc_type=doc,
            version=latest.version + 1,
            cache_key="edit:" + hashlib.sha256(material.encode()).hexdigest()[:24],
            content=content,
            fact_check=check,
            usage_event_ids=[],
        )
        session.add(row)
        await session.execute(
            delete(KitVersion).where(
                KitVersion.user_id == user_id,
                KitVersion.job_id == jid,
                KitVersion.track_id == track_id,
                KitVersion.doc_type == doc,
                KitVersion.version <= row.version - MAX_VERSIONS,
            )
        )
        await session.commit()
        await session.refresh(row)
        profile = await latest_profile(session, user_id)
        current = (profile.id, profile.version) if profile else None
        return _out(row, track, current)


def _name(value: object) -> object:
    return _clean(value) if isinstance(value, str) else value


class ExportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["pdf", "docx"]
    name: Annotated[str, BeforeValidator(_name), Field(min_length=1, max_length=80)]
    contact: Annotated[str, BeforeValidator(_name), Field(max_length=200)] = ""


class ExportOut(BaseModel):
    """A file, in base64: the web server's engine client reads JSON only."""

    model_config = ConfigDict(populate_by_name=True)

    filename: str
    content_type: str = Field(serialization_alias="contentType")
    data: str
    # Characters the PDF font cannot draw, shown as `?`. Always 0 for a DOCX.
    replaced: int = 0


_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}


async def export_kit(
    *,
    user_id: uuid.UUID,
    job_id: str,
    kit_id: str,
    body: dict[str, object],
    database: Database,
) -> ExportOut:
    """Make a PDF or DOCX of one saved version, on demand. Nothing is saved.

    The version is checked again against the facts the person has confirmed or edited
    now, so an export is never built from a stale check: a statement still flagged
    refuses the export (`needs_fixing`) until it is removed or edited, or its fact is.
    """
    jid = _id(job_id)
    kid = _id(kit_id)
    wanted: ExportIn = _validated(ExportIn, body)
    async with AsyncSession(database.engine) as session:
        job = await _owned_job(session, user_id, jid)
        row = await session.scalar(
            select(KitVersion).where(
                KitVersion.id == kid,
                KitVersion.user_id == user_id,
                KitVersion.job_id == jid,
            )
        )
        track = (
            await session.scalar(
                select(Track).where(Track.id == row.track_id, Track.user_id == user_id)
            )
            if row is not None
            else None
        )
        if row is None or track is None or track.kind != job.kind:
            raise not_found()
        facts = await load_facts(session, user_id, row.profile_id)
        content, check = kit_edit.recheck(
            row.content, facts, int(row.fact_check.get("omitted", 0))
        )
        company, doc_type = job.company, row.doc_type
    flagged = int(check["flagged"])
    if flagged:
        need = "statement still needs" if flagged == 1 else "statements still need"
        raise ApiError(
            409,
            "needs_fixing",
            f"{flagged} {need} you. Edit or remove them, or fix the fact they cite.",
        )
    label = kit_export.DOC_LABELS[doc_type]
    doc = kit_export.build_doc(content, wanted.name, wanted.contact, label)
    render = kit_export.render_pdf if wanted.format == "pdf" else kit_export.render_docx
    data = await asyncio.to_thread(render, doc)
    replaced = (
        await asyncio.to_thread(kit_export.count_undrawable, doc)
        if wanted.format == "pdf"
        else 0
    )
    # Cut the stem, not the whole name, so the extension always survives.
    stem = clean_filename(
        f"{wanted.name} - {label} - {company}", limit=150 - len(wanted.format) - 1
    ).rstrip()
    filename = f"{stem or 'document'}.{wanted.format}"
    return ExportOut(
        filename=filename,
        content_type=_CONTENT_TYPES[wanted.format],
        data=base64.b64encode(data).decode("ascii"),
        replaced=replaced,
    )
