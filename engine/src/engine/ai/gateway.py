"""Run one model task for one user.

Validate the input, reuse a cached result if there is one, otherwise call the
configured model, validate the JSON reply (one retry), write a usage row for every
response and cache the validated output. Prompts, inputs and outputs are never
logged and never written to the ledger.
"""

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from engine.ai.config import Env, ModelSetting, cost_usd, create_provider, read_tier
from engine.ai.errors import AiInputInvalidError, AiOutputInvalidError
from engine.ai.json import parse_model_output
from engine.ai.provider import AiProvider, AiRequest
from engine.ai.tasks import AiTask
from engine.db import Database
from engine.models import AiCache, UsageEvent

log = logging.getLogger("engine")

_JSON_INSTRUCTION = (
    "Reply with a single JSON object and nothing else: no prose, no code fences."
)


@dataclass(frozen=True)
class RunResult[O: BaseModel]:
    output: O
    cache_hit: bool
    prompt_version: str
    usage_event_id: uuid.UUID


def canonical_json(value: Any) -> str:
    """JSON with object keys sorted, so equal inputs always hash equally.

    NaN and infinity are refused rather than collapsed, so two different inputs can
    never share a cache key.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def cache_key_for(task: str, prompt_version: str, model: str, input_: Any) -> str:
    material = canonical_json(
        {
            "task": task,
            "promptVersion": prompt_version,
            "model": model,
            "input": input_,
        }
    )
    return hashlib.sha256(material.encode()).hexdigest()


@dataclass(frozen=True)
class _Ledger:
    """The ledger columns that stay the same for every row of one run."""

    user_id: uuid.UUID
    workflow: str
    provider: str
    model: str
    prompt_version: str


async def _record(
    database: Database,
    base: _Ledger,
    *,
    tokens_in: int,
    tokens_out: int,
    cost: Decimal | None,
    cache_hit: bool,
) -> uuid.UUID:
    async with AsyncSession(database.engine, expire_on_commit=False) as session:
        row = UsageEvent(
            user_id=base.user_id,
            workflow=base.workflow,
            provider=base.provider,
            model=base.model,
            prompt_version=base.prompt_version,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            cache_hit=cache_hit,
        )
        session.add(row)
        await session.flush()
        event_id = row.id
        await session.commit()
    return event_id


async def _store(
    database: Database,
    task: AiTask[Any, Any],
    user_id: uuid.UUID,
    key: str,
    output: BaseModel,
    setting: ModelSetting,
) -> None:
    """Cache the validated output. Best effort: the answer is already paid for.

    A failure is logged with a code only, because the database error text can carry
    the model output.
    """
    stored = output.model_dump(mode="json")
    try:
        statement = insert(AiCache).values(
            user_id=user_id,
            cache_key=key,
            task=task.name,
            prompt_version=task.prompt_version,
            output=stored,
        )
        async with AsyncSession(database.engine) as session:
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=["user_id", "cache_key"],
                    set_={"output": stored, "created_at": func.now()},
                )
            )
            await session.commit()
    except Exception:
        log.warning(
            "ai cache write failed",
            extra={
                "task": task.name,
                "provider": setting.provider,
                "model": setting.model,
                "code": "ai_cache_write_failed",
            },
        )


async def run_task[I: BaseModel, O: BaseModel](
    task: AiTask[I, O],
    raw_input: object,
    *,
    user_id: uuid.UUID,
    database: Database,
    env: Env | None = None,
    provider: AiProvider | None = None,
) -> RunResult[O]:
    started = time.monotonic()

    try:
        task_input = task.input_model.model_validate(raw_input)
    except ValidationError:
        raise AiInputInvalidError from None

    setting = read_tier(task.tier, env)
    model_id = f"{setting.provider}/{setting.model}"
    try:
        key = cache_key_for(
            task.name,
            task.prompt_version,
            model_id,
            task_input.model_dump(mode="json"),
        )
    except ValueError:
        raise AiInputInvalidError from None
    base = _Ledger(
        user_id=user_id,
        workflow=task.workflow,
        provider=setting.provider,
        model=setting.model,
        prompt_version=task.prompt_version,
    )

    if task.cache:
        async with AsyncSession(database.engine) as session:
            cached = await session.scalar(
                select(AiCache.output).where(
                    AiCache.user_id == user_id, AiCache.cache_key == key
                )
            )
        if cached is not None:
            try:
                hit = task.output_model.model_validate(cached)
            except ValidationError:
                hit = None  # a stored value that no longer fits is a miss
            if hit is not None:
                event_id = await _record(
                    database,
                    base,
                    tokens_in=0,
                    tokens_out=0,
                    cost=Decimal(0),
                    cache_hit=True,
                )
                log.info(
                    "ai task",
                    extra={
                        "task": task.name,
                        "provider": setting.provider,
                        "model": setting.model,
                        "cacheHit": True,
                        "durationMs": round((time.monotonic() - started) * 1000),
                    },
                )
                return RunResult(hit, True, task.prompt_version, event_id)

    adapter = provider or create_provider(setting, env)
    system = f"{task.system}\n\n{_JSON_INSTRUCTION}"
    user_message = task.user(task_input)
    message = user_message

    for attempt in (1, 2):
        response = await adapter.complete(
            AiRequest(
                model=setting.model,
                system=system,
                user=message,
                timeout_s=task.timeout_s,
            )
        )
        event_id = await _record(
            database,
            base,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost=cost_usd(response.tokens_in, response.tokens_out, setting.price),
            cache_hit=False,
        )

        parsed = parse_model_output(response.text, task.output_model)
        if parsed.ok and parsed.value is not None:
            if task.cache:
                await _store(database, task, user_id, key, parsed.value, setting)
            log.info(
                "ai task",
                extra={
                    "task": task.name,
                    "provider": setting.provider,
                    "model": setting.model,
                    "cacheHit": False,
                    "attempts": attempt,
                    "durationMs": round((time.monotonic() - started) * 1000),
                },
            )
            return RunResult(parsed.value, False, task.prompt_version, event_id)

        log.warning(
            "ai output rejected",
            extra={
                "task": task.name,
                "provider": setting.provider,
                "model": setting.model,
                "attempt": attempt,
                "reason": parsed.reason,
            },
        )
        message = (
            f"{user_message}\n\nYour previous reply was rejected: {parsed.reason}. "
            "Reply again with only a valid JSON object."
        )
    raise AiOutputInvalidError
