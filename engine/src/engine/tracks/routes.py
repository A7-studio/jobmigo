"""The track routes. Auth is applied by the parent router."""

from typing import Any

from fastapi import APIRouter, Request, Response

from engine.auth import CurrentUser
from engine.profile.routes import _body, _database
from engine.tracks import service
from engine.tracks.models import TrackOut

router = APIRouter()


@router.get("")
async def list_tracks(request: Request, user_id: CurrentUser) -> list[TrackOut]:
    return await service.list_tracks(user_id=user_id, database=_database(request))


@router.post("", status_code=201)
async def create_track(request: Request, user_id: CurrentUser) -> TrackOut:
    return await service.create_track(
        user_id=user_id, body=await _body(request), database=_database(request)
    )


@router.patch("/{track_id}")
async def rename_track(
    request: Request, track_id: str, user_id: CurrentUser
) -> TrackOut:
    return await service.rename_track(
        user_id=user_id,
        track_id=track_id,
        body=await _body(request),
        database=_database(request),
    )


@router.delete("/{track_id}", status_code=204)
async def delete_track(
    request: Request, track_id: str, user_id: CurrentUser
) -> Response:
    await service.delete_track(
        user_id=user_id, track_id=track_id, database=_database(request)
    )
    return Response(status_code=204)


def _toggle(on: bool) -> Any:
    async def handler(
        request: Request, track_id: str, kind: str, item_id: str, user_id: CurrentUser
    ) -> TrackOut:
        return await service.emphasise(
            user_id=user_id,
            track_id=track_id,
            kind=kind,
            item_id=item_id,
            on=on,
            database=_database(request),
        )

    return handler


router.put("/{track_id}/items/{kind}/{item_id}", response_model=TrackOut)(_toggle(True))
router.delete("/{track_id}/items/{kind}/{item_id}", response_model=TrackOut)(
    _toggle(False)
)
