"""Writes a kit for an invented job and profile once with the real strong model.

Skipped unless AI_LIVE_TEST=1, so Verify never spends money or needs a network:
    AI_LIVE_TEST=1 uv run --env-file ../.env pytest tests/test_kitting_live.py
Needs the strong tier configured (AI_STRONG_MODEL). Everything below is invented; no
real personal data is sent. The model may write flagged blocks: the test only checks
that the documents come back in the stored shape.
"""

import os
import uuid

import asyncpg
import pytest

from engine.db import Database
from engine.jobs.kitting import generate_kit
from tests.db import upgrade
from tests.profile_seed import seed_profile

LIVE = os.environ.get("AI_LIVE_TEST") == "1"
USER = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")
POSTING = """\
Senior Flutter Engineer at Lumen Health (remote, EMEA)

Requirements
- 4+ years of Flutter and Dart
- Experience shipping an app to both stores
We pay USD 3,000 to 4,500 per month.
"""


@pytest.mark.skipif(not LIVE, reason="set AI_LIVE_TEST=1 to call the real providers")
async def test_an_invented_job_gets_a_checked_kit(db_url: str) -> None:
    await upgrade(db_url)
    seeded = await seed_profile(db_url, USER)
    connection = await asyncpg.connect(db_url)
    job, track = uuid.uuid4(), uuid.uuid4()
    try:
        for table in ("skill", "experience"):
            await connection.execute(
                f"update engine.{table} set status = 'confirmed'"  # noqa: S608
                " where profile_id = $1",
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
            "insert into engine.track (id, user_id, name) values ($1, $2, 'Mobile')",
            track,
            USER,
        )
    finally:
        await connection.close()
    database = Database(db_url)
    try:
        docs = await generate_kit(
            user_id=USER,
            job_id=str(job),
            body={"trackId": str(track), "questions": ["Why do you want this role?"]},
            database=database,
        )
    finally:
        await database.dispose()
    assert [d.doc_type for d in docs] == ["cv", "letter", "answers"]
    for doc in docs:
        assert doc.fact_check["blocks"] >= 1
        assert doc.version == 1
