"""Evaluates an invented job against an invented profile once with the real models.

Skipped unless AI_LIVE_TEST=1, so Verify never spends money or needs a network:
    AI_LIVE_TEST=1 uv run --env-file ../.env pytest tests/test_evaluating_live.py
Needs both tiers configured (AI_CHEAP_MODEL and AI_STRONG_MODEL). Everything below is
invented; no real personal data is sent.
"""

import os
import uuid

import asyncpg
import pytest

from engine.db import Database
from engine.jobs.evaluating import evaluate_job
from tests.db import fetch, upgrade
from tests.profile_seed import seed_profile

LIVE = os.environ.get("AI_LIVE_TEST") == "1"
USER = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")
POSTING = """\
Senior Flutter Engineer at Lumen Health (remote, EMEA)

Requirements
- 4+ years of Flutter and Dart
- Experience shipping an app to both stores
Nice to have
- Experience with Swift platform channels
We pay USD 3,000 to 4,500 per month.
"""


@pytest.mark.skipif(not LIVE, reason="set AI_LIVE_TEST=1 to call the real providers")
async def test_an_invented_job_gets_a_checked_evaluation(db_url: str) -> None:
    await upgrade(db_url)
    seeded = await seed_profile(db_url, USER)
    connection = await asyncpg.connect(db_url)
    job, track = uuid.uuid4(), uuid.uuid4()
    try:
        await connection.execute(
            "update engine.skill set status = 'confirmed' where profile_id = $1",
            seeded.profile_id,
        )
        await connection.execute(
            "insert into engine.job (id, user_id, company, title, dedupe_key, "
            "description) values ($1, $2, 'Lumen Health', 'Senior Flutter Engineer', "
            "$3, $4)",
            job,
            USER,
            f"live-{job}",
            POSTING,
        )
        await connection.execute(
            "insert into engine.track (id, user_id, name, salary_floor, currency) "
            "values ($1, $2, 'Mobile', 1000, 'USD')",
            track,
            USER,
        )
    finally:
        await connection.close()
    database = Database(db_url)
    try:
        result = await evaluate_job(
            user_id=USER,
            job_id=str(job),
            body={"trackId": str(track)},
            database=database,
        )
    finally:
        await database.dispose()
    assert result.band in ("strong", "good", "stretch", "poor")
    assert result.requirements
    for requirement in result.requirements:
        if requirement.status in ("met", "partial"):
            assert requirement.evidence  # never a match without a cited fact
    rows = await fetch(
        db_url,
        "select workflow from engine.usage_event where user_id = $1 "
        "order by created_at",
        USER,
    )
    assert [row["workflow"] for row in rows] == ["evaluate", "evaluate"]
