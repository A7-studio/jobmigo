"""Parses a synthetic CV once with the real cheap-tier provider.

Skipped unless AI_LIVE_TEST=1, so Verify never spends money or needs a network:
    AI_LIVE_TEST=1 uv run --env-file ../.env pytest tests/test_cv_parse_live.py
The CV below is invented; no real personal data is sent.
"""

import os
import uuid

import pytest

from engine.cv.parse import parse_cv_text
from engine.db import Database
from tests.db import fetch, upgrade

LIVE = os.environ.get("AI_LIVE_TEST") == "1"

CV = """\
Alex Example
Mobile engineer

Experience
Northwind Apps, Senior Flutter Engineer, March 2021 to present
- Built the offline-first booking app used by 40,000 people
- Cut cold start time by 35%

Brightside Labs, Android Developer, 2018 to 2021
- Maintained a Kotlin payments SDK

Skills: Flutter, Dart, Kotlin, Firebase

Education
University of Example, BSc Computer Science, 2014 to 2018
"""


@pytest.mark.skipif(not LIVE, reason="set AI_LIVE_TEST=1 to call the real provider")
async def test_a_synthetic_cv_parses_into_a_valid_draft(db_url: str) -> None:
    await upgrade(db_url)
    database = Database(db_url)
    user = uuid.uuid4()
    try:
        draft = await parse_cv_text(CV, user_id=user, database=database)
    finally:
        await database.dispose()
    companies = {item.company.lower() for item in draft.experiences}
    assert any("northwind" in name for name in companies)
    assert any(skill.lower() == "flutter" for skill in draft.skills)
    assert draft.education
    rows = await fetch(
        db_url,
        "select workflow, tokens_in from engine.usage_event where user_id = $1",
        user,
    )
    assert [row["workflow"] for row in rows] == ["parse"]
