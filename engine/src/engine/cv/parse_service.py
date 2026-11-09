"""Start, run and read a CV parse. Every statement filters on the user id.

A parse is claimed atomically (`extracted` or `failed` to `parsing`), runs as an
in-process task, and writes the whole draft and the `parsed` status in one
transaction. This assumes one engine process: a restart leaves rows in `parsing`,
which `sweep_interrupted` turns into a retryable failure at the next start.
Nothing here logs CV text, names or model replies.
"""

import asyncio
import logging
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from engine.ai.config import Env, create_provider, read_tier
from engine.ai.errors import (
    AiInputInvalidError,
    AiNotConfiguredError,
    AiOutputInvalidError,
    AiUnavailableError,
)
from engine.ai.provider import AiProvider
from engine.cv.parse import ParsedProfile, ParseError, parse_cv_text
from engine.cv.service import CvOut, not_found, parse_id
from engine.db import Database
from engine.models import (
    Achievement,
    CvFile,
    Education,
    Experience,
    Profile,
    Project,
    Skill,
)

log = logging.getLogger("engine")

Status = Literal["extracted", "parsing", "parsed", "failed"]


class _Out(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ExperienceOut(_Out):
    id: uuid.UUID
    company: str
    role: str
    start: str | None
    end: str | None
    is_current: bool = Field(alias="isCurrent")
    bullets: list[str]
    status: str


class SkillOut(_Out):
    id: uuid.UUID
    name: str
    status: str


class AchievementOut(_Out):
    id: uuid.UUID
    text: str
    experience_id: uuid.UUID | None = Field(alias="experienceId")
    status: str


class ProjectOut(_Out):
    id: uuid.UUID
    name: str
    description: str | None
    status: str


class EducationOut(_Out):
    id: uuid.UUID
    institution: str
    qualification: str | None
    start: str | None
    end: str | None
    status: str


class DraftOut(_Out):
    id: uuid.UUID
    cv_id: uuid.UUID = Field(alias="cvId")
    headline: str | None
    summary: str | None
    experiences: list[ExperienceOut]
    skills: list[SkillOut]
    achievements: list[AchievementOut]
    projects: list[ProjectOut]
    education: list[EducationOut]


def failure_code(error: BaseException) -> str:
    """The stable code stored for a failed parse. Never a message."""
    if isinstance(error, ParseError):
        return error.code
    if isinstance(error, AiNotConfiguredError):
        return "ai_not_configured"
    if isinstance(error, AiUnavailableError):
        return "ai_unavailable"
    if isinstance(error, AiOutputInvalidError):
        return "ai_output_invalid"
    if isinstance(error, AiInputInvalidError):
        return "ai_input_invalid"
    return "internal"


def preflight(env: Env | None = None) -> None:
    """Fail with `ai_not_configured` before a claim when the cheap tier is unusable."""
    create_provider(read_tier("cheap", env), env)


async def get_cv(*, user_id: uuid.UUID, cv_id: str, database: Database) -> CvOut:
    wanted = parse_id(cv_id)
    async with AsyncSession(database.engine) as session:
        row = (
            await session.execute(
                select(
                    CvFile.id,
                    CvFile.filename,
                    CvFile.mime,
                    CvFile.size_bytes,
                    CvFile.parse_status,
                    CvFile.parse_error,
                    CvFile.created_at,
                ).where(CvFile.id == wanted, CvFile.user_id == user_id)
            )
        ).one_or_none()
    if row is None:
        raise not_found()
    return CvOut.model_validate(row, from_attributes=True)


async def claim(*, user_id: uuid.UUID, cv_id: uuid.UUID, database: Database) -> bool:
    """Move an `extracted` or `failed` CV to `parsing`; False if not claimable."""
    async with AsyncSession(database.engine) as session:
        claimed = await session.scalar(
            update(CvFile)
            .where(
                CvFile.id == cv_id,
                CvFile.user_id == user_id,
                CvFile.parse_status.in_(("extracted", "failed")),
            )
            .values(parse_status="parsing", parse_error=None, updated_at=func.now())
            .returning(CvFile.id)
        )
        await session.commit()
    return claimed is not None


async def mark_failed(
    *, user_id: uuid.UUID, cv_id: uuid.UUID, code: str, database: Database
) -> None:
    async with AsyncSession(database.engine) as session:
        await session.execute(
            update(CvFile)
            .where(
                CvFile.id == cv_id,
                CvFile.user_id == user_id,
                CvFile.parse_status == "parsing",
            )
            .values(parse_status="failed", parse_error=code, updated_at=func.now())
        )
        await session.commit()


async def sweep_interrupted(database: Database) -> int:
    """Fail every CV still `parsing`: the process that was parsing it is gone."""
    async with AsyncSession(database.engine) as session:
        result = await session.execute(
            update(CvFile)
            .where(CvFile.parse_status == "parsing")
            .values(
                parse_status="failed", parse_error="interrupted", updated_at=func.now()
            )
            .returning(CvFile.id)
        )
        await session.commit()
    return len(result.all())


async def _write_draft(
    *,
    user_id: uuid.UUID,
    cv_id: uuid.UUID,
    draft: ParsedProfile,
    database: Database,
) -> bool:
    """Write the draft and set `parsed` in one transaction. False if the CV is gone."""
    async with AsyncSession(database.engine) as session:
        updated = await session.scalar(
            update(CvFile)
            .where(
                CvFile.id == cv_id,
                CvFile.user_id == user_id,
                CvFile.parse_status == "parsing",
            )
            .values(parse_status="parsed", parse_error=None, updated_at=func.now())
            .returning(CvFile.id)
        )
        if updated is None:
            return False  # deleted or reset while the model was working
        profile = Profile(
            user_id=user_id,
            source_cv_id=cv_id,
            headline=draft.headline,
            summary=draft.summary,
        )
        session.add(profile)
        await session.flush()
        experiences = [
            Experience(
                user_id=user_id,
                profile_id=profile.id,
                position=index,
                company=item.company,
                role=item.role,
                start=item.start,
                end=item.end,
                is_current=item.is_current,
                bullets=list(item.bullets),
            )
            for index, item in enumerate(draft.experiences)
        ]
        session.add_all(experiences)
        await session.flush()
        session.add_all(
            Skill(user_id=user_id, profile_id=profile.id, position=i, name=name)
            for i, name in enumerate(draft.skills)
        )
        session.add_all(
            Achievement(
                user_id=user_id,
                profile_id=profile.id,
                position=i,
                text=item.text,
                experience_id=(
                    experiences[item.experience_index].id
                    if item.experience_index is not None
                    else None
                ),
            )
            for i, item in enumerate(draft.achievements)
        )
        session.add_all(
            Project(
                user_id=user_id,
                profile_id=profile.id,
                position=i,
                name=item.name,
                description=item.description,
            )
            for i, item in enumerate(draft.projects)
        )
        session.add_all(
            Education(
                user_id=user_id,
                profile_id=profile.id,
                position=i,
                institution=item.institution,
                qualification=item.qualification,
                start=item.start,
                end=item.end,
            )
            for i, item in enumerate(draft.education)
        )
        await session.commit()
    return True


async def run_parse(
    *,
    user_id: uuid.UUID,
    cv_id: uuid.UUID,
    database: Database,
    env: Env | None = None,
    provider: AiProvider | None = None,
) -> None:
    """Parse one claimed CV. Ends with `parsed`, `failed`, or nothing if it is gone."""
    try:
        async with AsyncSession(database.engine) as session:
            text = await session.scalar(
                select(CvFile.extracted_text).where(
                    CvFile.id == cv_id,
                    CvFile.user_id == user_id,
                    CvFile.parse_status == "parsing",
                )
            )
        if text is None:
            return
        draft = await parse_cv_text(
            text, user_id=user_id, database=database, env=env, provider=provider
        )
        await _write_draft(user_id=user_id, cv_id=cv_id, draft=draft, database=database)
    except asyncio.CancelledError:
        raise  # shutdown: the row stays `parsing` and the next start sweeps it
    except Exception as error:
        code = failure_code(error)
        log.warning(
            "cv parse failed", extra={"code": code, "error": type(error).__name__}
        )
        try:
            await mark_failed(
                user_id=user_id, cv_id=cv_id, code=code, database=database
            )
        except Exception:
            log.warning("cv parse status update failed")


class ParseJobs:
    """The running parse tasks, kept so they are not garbage collected."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self._tasks: set[asyncio.Task[None]] = set()

    def start(
        self,
        user_id: uuid.UUID,
        cv_id: uuid.UUID,
        *,
        env: Env | None = None,
        provider: AiProvider | None = None,
    ) -> asyncio.Task[None]:
        task = asyncio.create_task(
            run_parse(
                user_id=user_id,
                cv_id=cv_id,
                database=self._database,
                env=env,
                provider=provider,
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def shutdown(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def start_parse(
    *,
    user_id: uuid.UUID,
    cv_id: str,
    database: Database,
    jobs: ParseJobs,
    env: Env | None = None,
    provider: AiProvider | None = None,
) -> CvOut:
    """Start a parse (or retry a failed one). Idempotent for `parsing` and `parsed`."""
    current = await get_cv(user_id=user_id, cv_id=cv_id, database=database)
    if current.parse_status in ("parsing", "parsed"):
        return current
    if provider is None:
        preflight(env)
    wanted = parse_id(cv_id)
    if await claim(user_id=user_id, cv_id=wanted, database=database):
        jobs.start(user_id, wanted, env=env, provider=provider)
    return await get_cv(user_id=user_id, cv_id=cv_id, database=database)


async def get_draft(*, user_id: uuid.UUID, cv_id: str, database: Database) -> DraftOut:
    wanted = parse_id(cv_id)
    async with AsyncSession(database.engine) as session:
        profile = (
            await session.execute(
                select(Profile).where(
                    Profile.source_cv_id == wanted, Profile.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if profile is None:
            raise not_found()

        async def rows(model: Any) -> list[Any]:
            result = await session.execute(
                select(model)
                .where(model.profile_id == profile.id, model.user_id == user_id)
                .order_by(model.position)
            )
            return list(result.scalars())

        return DraftOut(
            id=profile.id,
            cv_id=profile.source_cv_id,
            headline=profile.headline,
            summary=profile.summary,
            experiences=[
                ExperienceOut.model_validate(r) for r in await rows(Experience)
            ],
            skills=[SkillOut.model_validate(r) for r in await rows(Skill)],
            achievements=[
                AchievementOut.model_validate(r) for r in await rows(Achievement)
            ],
            projects=[ProjectOut.model_validate(r) for r in await rows(Project)],
            education=[EducationOut.model_validate(r) for r in await rows(Education)],
        )
