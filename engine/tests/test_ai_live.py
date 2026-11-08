"""Calls the real provider once with your own keys.

Skipped unless AI_LIVE_TEST=1, so Verify never spends money or needs a network:
    AI_LIVE_TEST=1 uv run --env-file ../.env pytest tests/test_ai_live.py
"""

import os
import uuid

import pytest
from pydantic import BaseModel

from engine.ai.gateway import run_task
from engine.ai.tasks import AiTask
from engine.db import Database
from tests.db import fetch, upgrade

LIVE = os.environ.get("AI_LIVE_TEST") == "1"


class Question(BaseModel):
    question: str


class Answer(BaseModel):
    answer: float


TASK: AiTask[Question, Answer] = AiTask(
    name="live-check",
    workflow="screen",
    tier="cheap",
    prompt_version="v1",
    system="You answer arithmetic questions.",
    user=lambda i: f'{i.question} Return JSON like {{"answer": 4}}.',
    input_model=Question,
    output_model=Answer,
)


@pytest.mark.skipif(not LIVE, reason="set AI_LIVE_TEST=1 to call the real provider")
async def test_gets_a_validated_answer_records_usage_then_serves_the_cache(
    db_url: str,
) -> None:
    await upgrade(db_url)
    database = Database(db_url)
    user = uuid.uuid4()
    question = {"question": "What is 2 + 2?"}
    try:
        first = await run_task(TASK, question, user_id=user, database=database)
        assert first.output.answer == 4
        assert first.cache_hit is False
        second = await run_task(TASK, question, user_id=user, database=database)
        assert second.cache_hit is True
    finally:
        await database.dispose()
    rows = await fetch(
        db_url, "select tokens_in from engine.usage_event where user_id = $1", user
    )
    assert len(rows) == 2
    assert any(int(str(row["tokens_in"])) > 0 for row in rows)
