"""Read and edit the user's profile: their latest parsed draft.

Every statement filters on the user id. An item that belongs to an older draft is
treated as missing. Nothing here logs or echoes fact text.
"""

import uuid
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from engine.cv.parse_service import (
    AchievementOut,
    DraftOut,
    EducationOut,
    ExperienceOut,
    ProjectOut,
    SkillOut,
    load_draft,
)
from engine.cv.service import not_found
from engine.db import Database
from engine.errors import ApiError
from engine.models import CvFile, Experience, Profile, Skill, TrackProfileItem
from engine.profile.models import (
    INPUT,
    KINDS,
    MAX_ROWS,
    ROW,
    ProfileIn,
    current_values,
    row_values,
)


async def latest_profile(
    session: AsyncSession, user_id: uuid.UUID, *, lock: bool = False
) -> Profile | None:
    """The profile of the user's newest parsed CV, or None.

    With `lock`, the profile row is locked until the transaction ends, so edits to
    one profile run one at a time and none works from a stale read.
    """
    query = (
        select(Profile)
        .join(CvFile, CvFile.id == Profile.source_cv_id)
        .where(
            Profile.user_id == user_id,
            CvFile.user_id == user_id,
            CvFile.parse_status == "parsed",
        )
        .order_by(CvFile.created_at.desc(), CvFile.id.desc())
        .limit(1)
    )
    if lock:
        query = query.with_for_update(of=Profile)
    return (await session.execute(query)).scalar_one_or_none()


async def get_profile(*, user_id: uuid.UUID, database: Database) -> DraftOut:
    async with AsyncSession(database.engine) as session:
        profile = await latest_profile(session, user_id)
        if profile is None:
            raise not_found()
        return await load_draft(session, profile, user_id)


# ---- edits ----

OUT: dict[str, type[BaseModel]] = {
    "experience": ExperienceOut,
    "skill": SkillOut,
    "achievement": AchievementOut,
    "project": ProjectOut,
    "education": EducationOut,
}


def invalid() -> ApiError:
    return ApiError(422, "validation_failed", "The data is not valid.")


def _kind(kind: str) -> str:
    if kind not in KINDS:
        raise not_found()
    return kind


def _validated(model: Any, data: dict[str, Any]) -> Any:
    try:
        return model.model_validate(data)
    except ValidationError:
        raise invalid() from None  # never echo the input


async def _bump(session: AsyncSession, profile: Profile) -> None:
    await session.execute(
        update(Profile)
        .where(Profile.id == profile.id, Profile.user_id == profile.user_id)
        .values(version=Profile.version + 1, updated_at=func.now())
    )


async def _current(session: AsyncSession, user_id: uuid.UUID) -> Profile:
    """The profile to change, locked for this transaction."""
    profile = await latest_profile(session, user_id, lock=True)
    if profile is None:
        raise not_found()
    return profile


async def _item(
    session: AsyncSession, profile: Profile, kind: str, item_id: str
) -> Any:
    try:
        wanted = uuid.UUID(item_id)
    except ValueError:
        raise not_found() from None
    model = ROW[kind]
    row = (
        await session.execute(
            select(model).where(
                model.id == wanted,
                model.profile_id == profile.id,
                model.user_id == profile.user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise not_found()
    return row


async def _check_links(
    session: AsyncSession, profile: Profile, kind: str, values: dict[str, Any]
) -> None:
    """An achievement may link only to an experience of this profile."""
    if kind != "achievement" or values.get("experience_id") is None:
        return
    found = await session.scalar(
        select(Experience.id).where(
            Experience.id == values["experience_id"],
            Experience.profile_id == profile.id,
            Experience.user_id == profile.user_id,
        )
    )
    if found is None:
        raise invalid()


async def _duplicate_skill(
    session: AsyncSession, profile: Profile, name: str, except_id: uuid.UUID | None
) -> None:
    query = select(Skill.id, Skill.name).where(
        Skill.profile_id == profile.id, Skill.user_id == profile.user_id
    )
    wanted = name.casefold()
    for skill_id, existing in (await session.execute(query)).all():
        if skill_id != except_id and existing.casefold() == wanted:
            raise ApiError(
                409, "already_exists", "That skill is already in your profile."
            )


async def patch_profile(
    *, user_id: uuid.UUID, body: dict[str, Any], database: Database
) -> DraftOut:
    async with AsyncSession(database.engine) as session:
        profile = await _current(session, user_id)
        if not body:
            raise invalid()
        merged = {"headline": profile.headline, "summary": profile.summary} | body
        parsed = _validated(ProfileIn, merged)
        changed = (parsed.headline, parsed.summary) != (
            profile.headline,
            profile.summary,
        )
        if changed:
            await session.execute(
                update(Profile)
                .where(Profile.id == profile.id, Profile.user_id == user_id)
                .values(
                    headline=parsed.headline,
                    summary=parsed.summary,
                    version=Profile.version + 1,
                    updated_at=func.now(),
                )
            )
            await session.commit()
            session.expire_all()
            profile = await _current(session, user_id)
        return await load_draft(session, profile, user_id)


async def add_item(
    *,
    user_id: uuid.UUID,
    kind: str,
    body: dict[str, Any],
    database: Database,
) -> Any:
    kind = _kind(kind)
    async with AsyncSession(database.engine) as session:
        profile = await _current(session, user_id)
        parsed = _validated(INPUT[kind], body)
        values = row_values(kind, parsed)
        model = ROW[kind]
        count = (
            await session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.profile_id == profile.id, model.user_id == user_id)
            )
        ) or 0
        if count >= MAX_ROWS[kind]:
            raise ApiError(422, "limit_reached", "There are too many of these already.")
        if kind == "skill":
            await _duplicate_skill(session, profile, values["name"], None)
        await _check_links(session, profile, kind, values)
        last = await session.scalar(
            select(func.max(model.position)).where(
                model.profile_id == profile.id, model.user_id == user_id
            )
        )
        row = model(
            user_id=user_id,
            profile_id=profile.id,
            position=0 if last is None else last + 1,
            status="edited",
            **values,
        )
        session.add(row)
        await _bump(session, profile)
        await session.commit()
        await session.refresh(row)
        return OUT[kind].model_validate(row)


async def patch_item(
    *,
    user_id: uuid.UUID,
    kind: str,
    item_id: str,
    body: dict[str, Any],
    database: Database,
) -> Any:
    kind = _kind(kind)
    async with AsyncSession(database.engine) as session:
        profile = await _current(session, user_id)
        row = await _item(session, profile, kind, item_id)
        if not body:
            raise invalid()
        before = current_values(kind, row)
        parsed = _validated(INPUT[kind], before | body)
        values = row_values(kind, parsed)
        columns = {key: getattr(row, key) for key in values}
        if values == columns:
            return OUT[kind].model_validate(row)  # nothing changed
        if kind == "skill":
            await _duplicate_skill(session, profile, values["name"], row.id)
        await _check_links(session, profile, kind, values)
        for key, value in values.items():
            setattr(row, key, value)
        row.status = "edited"
        await _bump(session, profile)
        await session.commit()
        await session.refresh(row)
        return OUT[kind].model_validate(row)


async def confirm_item(
    *, user_id: uuid.UUID, kind: str, item_id: str, database: Database
) -> Any:
    kind = _kind(kind)
    async with AsyncSession(database.engine) as session:
        profile = await _current(session, user_id)
        row = await _item(session, profile, kind, item_id)
        if row.status == "extracted":
            row.status = "confirmed"
            await _bump(session, profile)
            await session.commit()
            await session.refresh(row)
        return OUT[kind].model_validate(row)


async def delete_item(
    *, user_id: uuid.UUID, kind: str, item_id: str, database: Database
) -> None:
    kind = _kind(kind)
    async with AsyncSession(database.engine) as session:
        profile = await _current(session, user_id)
        row = await _item(session, profile, kind, item_id)
        await session.execute(
            delete(TrackProfileItem).where(
                TrackProfileItem.user_id == user_id,
                TrackProfileItem.kind == kind,
                TrackProfileItem.item_id == row.id,
            )
        )
        await session.delete(row)
        await _bump(session, profile)
        await session.commit()


async def confirm_all(*, user_id: uuid.UUID, database: Database) -> dict[str, int]:
    async with AsyncSession(database.engine) as session:
        profile = await _current(session, user_id)
        confirmed = 0
        for model in ROW.values():
            result = await session.execute(
                update(model)
                .where(
                    model.profile_id == profile.id,
                    model.user_id == user_id,
                    model.status == "extracted",
                )
                .values(status="confirmed")
                .returning(model.id)
            )
            confirmed += len(result.all())
        if confirmed:
            await _bump(session, profile)
        await session.commit()
        session.expire_all()
        version = (await _current(session, user_id)).version
        return {"confirmed": confirmed, "version": version}
