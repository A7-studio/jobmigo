"""The shapes the user may send for each kind of fact, and how rows map to them.

The bounds and text cleaning are the parse rules (`cv/parse.py`), so a fact the user
types is held to the same limits as one the model proposed. Bodies use camelCase.
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from engine.cv import limits
from engine.cv.parse import (
    Achievement,
    Bullet,
    Date,
    Description,
    Headline,
    Name,
    OptionalName,
    ProjectName,
    Summary,
)
from engine.cv.parse import Skill as SkillName
from engine.models import (
    Achievement as AchievementRow,
)
from engine.models import (
    Education,
    Experience,
    Project,
    Skill,
)

KINDS = ("experience", "skill", "achievement", "project", "education")


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=False)


class ExperienceIn(_In):
    company: Name
    role: Name
    start: Date = None
    end: Date = None
    is_current: bool = Field(default=False, alias="isCurrent")
    bullets: list[Bullet] = Field(default_factory=list, max_length=limits.MAX_BULLETS)


class SkillIn(_In):
    name: SkillName


class AchievementIn(_In):
    text: Achievement
    experience_id: uuid.UUID | None = Field(default=None, alias="experienceId")


class ProjectIn(_In):
    name: ProjectName
    description: Description = None


class EducationIn(_In):
    institution: Name
    qualification: OptionalName = None
    start: Date = None
    end: Date = None


class ProfileIn(_In):
    headline: Headline = None
    summary: Summary = None


INPUT: dict[str, type[_In]] = {
    "experience": ExperienceIn,
    "skill": SkillIn,
    "achievement": AchievementIn,
    "project": ProjectIn,
    "education": EducationIn,
}
ROW: dict[str, Any] = {
    "experience": Experience,
    "skill": Skill,
    "achievement": AchievementRow,
    "project": Project,
    "education": Education,
}
MAX_ROWS = {
    "experience": limits.MAX_EXPERIENCES,
    "skill": limits.MAX_SKILLS,
    "achievement": limits.MAX_ACHIEVEMENTS,
    "project": limits.MAX_PROJECTS,
    "education": limits.MAX_EDUCATION,
}


def current_values(kind: str, row: Any) -> dict[str, Any]:
    """A row as the body that would produce it (wire names), for merging a patch."""
    if kind == "experience":
        return {
            "company": row.company,
            "role": row.role,
            "start": row.start,
            "end": row.end,
            "isCurrent": row.is_current,
            "bullets": list(row.bullets),
        }
    if kind == "skill":
        return {"name": row.name}
    if kind == "achievement":
        return {"text": row.text, "experienceId": row.experience_id}
    if kind == "project":
        return {"name": row.name, "description": row.description}
    return {
        "institution": row.institution,
        "qualification": row.qualification,
        "start": row.start,
        "end": row.end,
    }


def row_values(kind: str, parsed: _In) -> dict[str, Any]:
    """Column values from a validated body."""
    data = parsed.model_dump()
    if kind == "experience":
        data["bullets"] = list(data["bullets"])
    return data
