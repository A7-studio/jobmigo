"""Create, rename and delete tracks, and mark which facts a track emphasises.

Every statement filters on the user id. Only a confirmed or edited fact of the
user's latest parsed profile can be emphasised. Nothing here logs track names.
"""

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from engine.cv.service import not_found
from engine.db import Database
from engine.errors import ApiError
from engine.models import Track, TrackProfileItem
from engine.profile.models import KINDS, ROW
from engine.profile.service import _validated, latest_profile
from engine.tracks.models import MAX_TRACKS, TrackIn, TrackOut, track_out


def _exists() -> ApiError:
    return ApiError(409, "already_exists", "You already have a track with that name.")


def _id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise not_found() from None


async def _emphasis(
    session: AsyncSession, user_id: uuid.UUID, track_id: uuid.UUID
) -> list[tuple[str, uuid.UUID]]:
    rows = await session.execute(
        select(TrackProfileItem.kind, TrackProfileItem.item_id)
        .where(
            TrackProfileItem.track_id == track_id, TrackProfileItem.user_id == user_id
        )
        .order_by(TrackProfileItem.kind, TrackProfileItem.item_id)
    )
    return [(kind, item) for kind, item in rows.all()]


async def _locked(
    session: AsyncSession, user_id: uuid.UUID, track_id: uuid.UUID
) -> Track:
    track = (
        await session.execute(
            select(Track)
            .where(Track.id == track_id, Track.user_id == user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if track is None:
        raise not_found()
    return track


async def list_tracks(*, user_id: uuid.UUID, database: Database) -> list[TrackOut]:
    async with AsyncSession(database.engine) as session:
        tracks = (
            (
                await session.execute(
                    select(Track)
                    .where(Track.user_id == user_id)
                    .order_by(Track.created_at, Track.id)
                )
            )
            .scalars()
            .all()
        )
        return [
            track_out(track, await _emphasis(session, user_id, track.id))
            for track in tracks
        ]


async def create_track(
    *, user_id: uuid.UUID, body: dict[str, object], database: Database
) -> TrackOut:
    parsed = _validated(TrackIn, body)
    async with AsyncSession(database.engine) as session:
        # One lock per user keeps two creates from both passing the cap.
        await session.execute(
            select(func.pg_advisory_xact_lock(func.hashtext(str(user_id))))
        )
        count = await session.scalar(
            select(func.count()).select_from(Track).where(Track.user_id == user_id)
        )
        if (count or 0) >= MAX_TRACKS:
            raise ApiError(422, "limit_reached", "You have reached the track limit.")
        track = Track(user_id=user_id, name=parsed.name)
        session.add(track)
        try:
            await session.commit()
        except IntegrityError:
            raise _exists() from None
        await session.refresh(track)
        return track_out(track, [])


async def rename_track(
    *, user_id: uuid.UUID, track_id: str, body: dict[str, object], database: Database
) -> TrackOut:
    wanted = _id(track_id)
    parsed = _validated(TrackIn, body)
    async with AsyncSession(database.engine) as session:
        track = await _locked(session, user_id, wanted)
        if track.name != parsed.name:
            track.name = parsed.name
            track.variant_version += 1
            track.updated_at = func.now()
            try:
                await session.commit()
            except IntegrityError:
                raise _exists() from None
            await session.refresh(track)
        return track_out(track, await _emphasis(session, user_id, track.id))


async def delete_track(
    *, user_id: uuid.UUID, track_id: str, database: Database
) -> None:
    wanted = _id(track_id)
    async with AsyncSession(database.engine) as session:
        track = await _locked(session, user_id, wanted)
        await session.delete(track)
        await session.commit()


async def _fact_status(
    session: AsyncSession, user_id: uuid.UUID, kind: str, item_id: uuid.UUID
) -> str:
    """The status of a fact in the user's latest parsed profile, or not found."""
    profile = await latest_profile(session, user_id)
    if profile is None:
        raise not_found()
    model = ROW[kind]
    status = await session.scalar(
        select(model.status).where(
            model.id == item_id,
            model.profile_id == profile.id,
            model.user_id == user_id,
        )
    )
    if status is None:
        raise not_found()
    return str(status)


def _checked(kind: str, item_id: str) -> tuple[str, uuid.UUID]:
    if kind not in KINDS:
        raise not_found()
    return kind, _id(item_id)


async def emphasise(
    *,
    user_id: uuid.UUID,
    track_id: str,
    kind: str,
    item_id: str,
    on: bool,
    database: Database,
) -> TrackOut:
    wanted = _id(track_id)
    kind, item = _checked(kind, item_id)
    async with AsyncSession(database.engine) as session:
        track = await _locked(session, user_id, wanted)
        present = await session.scalar(
            select(TrackProfileItem.id).where(
                TrackProfileItem.track_id == track.id,
                TrackProfileItem.user_id == user_id,
                TrackProfileItem.kind == kind,
                TrackProfileItem.item_id == item,
            )
        )
        if on and present is None:
            status = await _fact_status(session, user_id, kind, item)
            if status == "extracted":
                raise ApiError(
                    422, "not_confirmed", "Confirm that fact before emphasising it."
                )
            session.add(
                TrackProfileItem(
                    user_id=user_id, track_id=track.id, kind=kind, item_id=item
                )
            )
            changed = True
        elif not on and present is not None:
            await session.execute(
                delete(TrackProfileItem).where(
                    TrackProfileItem.id == present, TrackProfileItem.user_id == user_id
                )
            )
            changed = True
        else:
            changed = False
        if changed:
            await session.execute(
                update(Track)
                .where(Track.id == track.id, Track.user_id == user_id)
                .values(
                    variant_version=Track.variant_version + 1, updated_at=func.now()
                )
            )
            await session.commit()
            session.expire_all()
            track = await _locked(session, user_id, wanted)
        return track_out(track, await _emphasis(session, user_id, track.id))
