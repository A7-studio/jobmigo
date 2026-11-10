"""The job preferences of a track: bounds, cleaning and the merge of a partial change.

Text is cleaned like profile facts. Lists keep their order and refuse repeats (ignoring
case), so a duplicate is an error the user sees instead of a silent merge.
"""

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from engine.cv.parse import _clean, _clean_or_none
from engine.models import Track

WORK_MODES = ("remote", "hybrid", "onsite")
Weight = Literal["must", "important", "nice"]


Text80 = Annotated[
    str, BeforeValidator(_clean), StringConstraints(min_length=1, max_length=80)
]
Text120 = Annotated[
    str, BeforeValidator(_clean), StringConstraints(min_length=1, max_length=120)
]


def _unique(items: list[str]) -> list[str]:
    seen = {item.casefold() for item in items}
    if len(seen) != len(items):
        raise ValueError("repeated item")
    return items


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Text120
    weight: Weight


class PreferencesIn(BaseModel):
    """Every field, camelCase on the wire. Defaults mean "no preference"."""

    model_config = ConfigDict(extra="forbid", populate_by_name=False)

    target_roles: list[Text80] = Field(
        default_factory=list, alias="targetRoles", max_length=10
    )
    salary_floor: int | None = Field(
        default=None, alias="salaryFloor", ge=0, le=10_000_000, strict=True
    )
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None
    work_modes: list[Literal["remote", "hybrid", "onsite"]] = Field(
        default_factory=list, alias="workModes", max_length=3
    )
    locations: list[Text80] = Field(default_factory=list, max_length=10)
    eligibility: Annotated[
        Annotated[str, StringConstraints(max_length=500)] | None,
        BeforeValidator(_clean_or_none),
    ] = None
    criteria: list[Criterion] = Field(default_factory=list, max_length=30)
    dealbreakers: list[Text120] = Field(default_factory=list, max_length=10)
    do_not_apply: list[Text80] = Field(
        default_factory=list, alias="doNotApply", max_length=50
    )

    @model_validator(mode="after")
    def _consistent(self) -> "PreferencesIn":
        _unique(self.target_roles)
        _unique(self.locations)
        _unique(self.dealbreakers)
        _unique(self.do_not_apply)
        _unique(list(self.work_modes))
        _unique([c.label for c in self.criteria])
        if self.salary_floor is not None and self.currency is None:
            raise ValueError("a salary floor needs a currency")
        return self


class PreferencesOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    target_roles: list[str] = Field(serialization_alias="targetRoles")
    salary_floor: int | None = Field(serialization_alias="salaryFloor")
    currency: str | None
    work_modes: list[str] = Field(serialization_alias="workModes")
    locations: list[str]
    eligibility: str | None
    criteria: list[Criterion]
    dealbreakers: list[str]
    do_not_apply: list[str] = Field(serialization_alias="doNotApply")


def current(track: Track) -> dict[str, Any]:
    """The stored preferences under their wire names, for merging a partial change."""
    return {
        "targetRoles": list(track.target_roles),
        "salaryFloor": track.salary_floor,
        "currency": track.currency,
        "workModes": list(track.work_modes),
        "locations": list(track.locations),
        "eligibility": track.eligibility,
        "criteria": [dict(c) for c in track.criteria],
        "dealbreakers": list(track.dealbreakers),
        "doNotApply": list(track.do_not_apply),
    }


def apply(track: Track, parsed: PreferencesIn) -> None:
    track.target_roles = list(parsed.target_roles)
    track.salary_floor = parsed.salary_floor
    track.currency = parsed.currency
    track.work_modes = list(parsed.work_modes)
    track.locations = list(parsed.locations)
    track.eligibility = parsed.eligibility
    track.criteria = [c.model_dump() for c in parsed.criteria]
    track.dealbreakers = list(parsed.dealbreakers)
    track.do_not_apply = list(parsed.do_not_apply)


def out(track: Track) -> PreferencesOut:
    return PreferencesOut(
        target_roles=list(track.target_roles),
        salary_floor=track.salary_floor,
        currency=track.currency,
        work_modes=list(track.work_modes),
        locations=list(track.locations),
        eligibility=track.eligibility,
        criteria=[Criterion.model_validate(c) for c in track.criteria],
        dealbreakers=list(track.dealbreakers),
        do_not_apply=list(track.do_not_apply),
    )
