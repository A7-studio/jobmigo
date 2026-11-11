"""The shapes of a track in and out. Bodies use camelCase."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from engine.cv.parse import _clean
from engine.models import Track
from engine.tracks.preferences import PreferencesOut, out

MAX_TRACKS = 10
MAX_NAME_CHARS = 60

TrackName = Annotated[
    str,
    BeforeValidator(_clean),
    StringConstraints(min_length=1, max_length=MAX_NAME_CHARS),
]


Kind = Literal["job", "gig", "ai_training"]


class TrackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: TrackName


class TrackCreate(TrackIn):
    """A new track. Its type cannot be changed afterwards."""

    kind: Kind = "job"


class EmphasisOut(BaseModel):
    kind: str
    item_id: uuid.UUID = Field(serialization_alias="itemId")


class TrackOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    name: str
    kind: str
    variant_version: int = Field(serialization_alias="variantVersion")
    emphasis: list[EmphasisOut]
    preferences: PreferencesOut


def track_out(track: Track, emphasis: list[tuple[str, uuid.UUID]]) -> TrackOut:
    return TrackOut(
        id=track.id,
        name=track.name,
        kind=track.kind,
        variant_version=track.variant_version,
        emphasis=[EmphasisOut(kind=kind, item_id=item) for kind, item in emphasis],
        preferences=out(track),
    )
