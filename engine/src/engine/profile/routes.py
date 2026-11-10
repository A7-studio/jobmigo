"""The profile routes. Auth is applied by the parent router."""

import json
from typing import Any

from fastapi import APIRouter, Request, Response

from engine.auth import CurrentUser
from engine.cv.parse_service import DraftOut
from engine.db import Database
from engine.profile import service
from engine.profile.service import invalid

router = APIRouter()
MAX_BODY_BYTES = 32 * 1024


def _database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


async def _body(request: Request) -> dict[str, Any]:
    """The JSON object sent, or a stable 422. Never echoes what was sent.

    The size is checked from the header first, then as the body streams in, so an
    oversized body is never buffered whole.
    """
    declared = request.headers.get("content-length")
    if (
        declared
        and declared.isascii()
        and declared.isdigit()
        and int(declared) > MAX_BODY_BYTES
    ):
        raise invalid()
    raw = bytearray()
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > MAX_BODY_BYTES:
            raise invalid()
    try:
        data = json.loads(bytes(raw))
    except (ValueError, RecursionError):  # bad JSON, or nesting too deep to parse
        raise invalid() from None
    if not isinstance(data, dict):
        raise invalid()
    return data


@router.get("")
async def read_profile(request: Request, user_id: CurrentUser) -> DraftOut:
    return await service.get_profile(user_id=user_id, database=_database(request))


@router.patch("")
async def update_profile(request: Request, user_id: CurrentUser) -> DraftOut:
    return await service.patch_profile(
        user_id=user_id, body=await _body(request), database=_database(request)
    )


@router.post("/confirm-all")
async def confirm_all(request: Request, user_id: CurrentUser) -> dict[str, int]:
    return await service.confirm_all(user_id=user_id, database=_database(request))


@router.post("/items/{kind}", status_code=201)
async def add_item(request: Request, kind: str, user_id: CurrentUser) -> Any:
    return await service.add_item(
        user_id=user_id,
        kind=kind,
        body=await _body(request),
        database=_database(request),
    )


@router.patch("/items/{kind}/{item_id}")
async def update_item(
    request: Request, kind: str, item_id: str, user_id: CurrentUser
) -> Any:
    return await service.patch_item(
        user_id=user_id,
        kind=kind,
        item_id=item_id,
        body=await _body(request),
        database=_database(request),
    )


@router.post("/items/{kind}/{item_id}/confirm")
async def confirm_item(
    request: Request, kind: str, item_id: str, user_id: CurrentUser
) -> Any:
    return await service.confirm_item(
        user_id=user_id, kind=kind, item_id=item_id, database=_database(request)
    )


@router.delete("/items/{kind}/{item_id}", status_code=204)
async def delete_item(
    request: Request, kind: str, item_id: str, user_id: CurrentUser
) -> Response:
    await service.delete_item(
        user_id=user_id, kind=kind, item_id=item_id, database=_database(request)
    )
    return Response(status_code=204)
