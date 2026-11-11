"""What the AI calls cost and how well they went: aggregates over the usage ledger.

Reads counts, tokens and money only. The ledger holds no text, and nothing here adds
any. Money is USD; a call with no configured price is counted as "cost unknown",
never as zero.
"""

import os
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy import ColumnElement, Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.ai.config import Env, Price, cost_usd
from engine.db import Database
from engine.models import UsageEvent

MAX_DAYS = 365
_CENT = Decimal("0.01")
_MICRO = Decimal("0.000001")


class _Out(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UsageRow(_Out):
    workflow: str
    provider: str
    model: str
    prompt_version: str
    calls: int = Field(description="Calls that reached the model; cache hits excluded.")
    cache_hits: int
    rejected: int
    failed: int
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    unknown_cost_calls: int
    avg_cost_usd: Decimal | None = Field(
        description="Average over calls with a usable answer and a known cost."
    )
    cache_savings_usd: Decimal


class WorkflowRow(_Out):
    workflow: str
    calls: int
    cache_hits: int
    rejected: int
    failed: int
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    unknown_cost_calls: int
    avg_cost_usd: Decimal | None


class Compare(_Out):
    label: str
    configured: bool
    estimate_usd: Decimal | None


class UsageReport(_Out):
    days: int
    since: datetime
    workflows: list[WorkflowRow]
    rows: list[UsageRow]
    total_cost_usd: Decimal
    unknown_cost_calls: int
    cache_savings_usd: Decimal
    compare: Compare
    golden_set: None = Field(
        default=None, description="Not run yet: the golden set is feature 8d."
    )


def _price(raw: str | None) -> Price | None:
    """`inputUsdPerMillion,outputUsdPerMillion`, or None when unset or unreadable."""
    if raw is None or not raw.strip():
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 2:
        return None
    try:
        numbers = [Decimal(p) for p in parts]
    except InvalidOperation:
        return None
    if any(not n.is_finite() or n < 0 for n in numbers):
        return None
    return Price(numbers[0], numbers[1])


def _avg(total: Decimal, n: int) -> Decimal | None:
    return (total / n).quantize(_MICRO, rounding=ROUND_HALF_UP) if n else None


async def usage_report(
    database: Database,
    *,
    days: int = 30,
    env: Env | None = None,
    now: datetime | None = None,
) -> UsageReport:
    """Aggregate the ledger for the last `days` days, across every user."""
    days = max(1, min(days, MAX_DAYS))
    since = (now or datetime.now(UTC)) - timedelta(days=days)
    live = ~UsageEvent.cache_hit
    good = live & (UsageEvent.outcome == "ok")
    known = good & UsageEvent.cost_usd.is_not(None)

    def count(condition: Any) -> ColumnElement[Any]:
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0).cast(Integer)

    def total(column: Any, condition: Any = live) -> ColumnElement[Any]:
        return func.coalesce(func.sum(case((condition, column), else_=0)), 0)

    statement = (
        select(
            UsageEvent.workflow,
            UsageEvent.provider,
            UsageEvent.model,
            UsageEvent.prompt_version,
            count(live).label("calls"),
            count(UsageEvent.cache_hit).label("cache_hits"),
            count(UsageEvent.outcome == "rejected").label("rejected"),
            count(UsageEvent.outcome == "failed").label("failed"),
            total(UsageEvent.tokens_in).label("tokens_in"),
            total(UsageEvent.tokens_out).label("tokens_out"),
            total(UsageEvent.cost_usd).label("cost"),
            count(live & UsageEvent.cost_usd.is_(None)).label("unknown"),
            total(UsageEvent.cost_usd, known).label("known_cost"),
            count(known).label("known_calls"),
        )
        .where(UsageEvent.created_at >= since)
        .group_by(
            UsageEvent.workflow,
            UsageEvent.provider,
            UsageEvent.model,
            UsageEvent.prompt_version,
        )
        .order_by(
            UsageEvent.workflow,
            UsageEvent.provider,
            UsageEvent.model,
            UsageEvent.prompt_version,
        )
    )
    async with AsyncSession(database.engine) as session:
        fetched = (await session.execute(statement)).all()

    rows: list[UsageRow] = []
    for r in fetched:
        avg = _avg(Decimal(r.known_cost), int(r.known_calls))
        savings = (avg * int(r.cache_hits)) if avg is not None else Decimal(0)
        rows.append(
            UsageRow(
                workflow=r.workflow,
                provider=r.provider,
                model=r.model,
                prompt_version=r.prompt_version,
                calls=int(r.calls),
                cache_hits=int(r.cache_hits),
                rejected=int(r.rejected),
                failed=int(r.failed),
                tokens_in=int(r.tokens_in),
                tokens_out=int(r.tokens_out),
                cost_usd=Decimal(r.cost).quantize(_MICRO),
                unknown_cost_calls=int(r.unknown),
                avg_cost_usd=avg,
                cache_savings_usd=savings.quantize(_MICRO, rounding=ROUND_HALF_UP),
            )
        )

    workflows: dict[str, WorkflowRow] = {}
    priced: dict[str, tuple[Decimal, int]] = {}
    for r, row in zip(fetched, rows, strict=True):
        cost, n = priced.get(row.workflow, (Decimal(0), 0))
        priced[row.workflow] = (cost + Decimal(r.known_cost), n + int(r.known_calls))
    for row in rows:
        w = workflows.get(row.workflow)
        if w is None:
            workflows[row.workflow] = WorkflowRow(
                workflow=row.workflow,
                calls=0,
                cache_hits=0,
                rejected=0,
                failed=0,
                tokens_in=0,
                tokens_out=0,
                cost_usd=Decimal(0),
                unknown_cost_calls=0,
                avg_cost_usd=None,
            )
            w = workflows[row.workflow]
        w.calls += row.calls
        w.cache_hits += row.cache_hits
        w.rejected += row.rejected
        w.failed += row.failed
        w.tokens_in += row.tokens_in
        w.tokens_out += row.tokens_out
        w.cost_usd += row.cost_usd
        w.unknown_cost_calls += row.unknown_cost_calls
    for w in workflows.values():
        w.avg_cost_usd = _avg(*priced[w.workflow])

    source = os.environ if env is None else env
    price = _price(source.get("AI_COMPARE_PRICE"))
    label = (source.get("AI_COMPARE_LABEL") or "").strip()[:60] or "a paid model"
    tokens_in = sum(r.tokens_in for r in rows)
    tokens_out = sum(r.tokens_out for r in rows)
    estimate = cost_usd(tokens_in, tokens_out, price)

    return UsageReport(
        days=days,
        since=since,
        workflows=list(workflows.values()),
        rows=rows,
        total_cost_usd=sum((r.cost_usd for r in rows), Decimal(0)).quantize(_CENT),
        unknown_cost_calls=sum(r.unknown_cost_calls for r in rows),
        cache_savings_usd=sum((r.cache_savings_usd for r in rows), Decimal(0)).quantize(
            _CENT
        ),
        compare=Compare(
            label=label,
            configured=price is not None,
            estimate_usd=estimate.quantize(_CENT) if estimate is not None else None,
        ),
    )
