"""The band, the main gap, the summary and the practical checks of an evaluation.

All of it is code: the model only judges each requirement against the user's facts, and
this module turns those judgements into the band the user sees. There is no score and no
percentage. The checks sit next to the band and never change it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from engine.jobs import gates

STRONG, GOOD, STRETCH, POOR = "strong", "good", "stretch", "poor"


@dataclass(frozen=True)
class Judged:
    """One requirement after the model's judgement and the code's checks."""

    need: str
    importance: str  # must | important | nice
    status: str  # met | partial | gap | unknown
    note: str = ""


def core(reqs: Sequence[Judged]) -> tuple[list[Judged], str]:
    """The requirements that decide the band, and what to call them.

    The must-haves; when the posting states none, the important ones; failing that, all.
    """
    musts = [r for r in reqs if r.importance == "must"]
    if musts:
        return musts, "must-haves"
    important = [r for r in reqs if r.importance == "important"]
    if important:
        return important, "important requirements"
    return list(reqs), "requirements"


def band_for(reqs: Sequence[Judged]) -> str:
    """Strong, good, stretch or poor ("Weak fit"). Raises on no requirements."""
    if not reqs:
        raise ValueError("no requirements")
    deciding, _ = core(reqs)
    gaps = sum(r.status == "gap" for r in deciding)
    bad = gaps + sum(r.status == "unknown" for r in deciding)
    if bad >= 2 or gaps * 2 > len(deciding):
        return POOR
    if bad == 1:
        return STRETCH
    musts_decide = any(r.importance == "must" for r in deciding)
    important_gap = musts_decide and any(
        r.importance == "important" and r.status == "gap" for r in reqs
    )
    if any(r.status == "partial" for r in deciding) or important_gap:
        return GOOD
    return STRONG


def main_gap(reqs: Sequence[Judged]) -> dict[str, str] | None:
    """The first deciding gap, else the first deciding unknown, else None."""
    deciding, _ = core(reqs)
    for status in ("gap", "unknown"):
        for r in deciding:
            if r.status == status:
                return {"need": r.need, "status": r.status, "note": r.note}
    return None


def summary(reqs: Sequence[Judged]) -> str:
    """One plain sentence, for example "Evidence for 6 of 7 must-haves"."""
    deciding, kind = core(reqs)
    have = sum(r.status in ("met", "partial") for r in deciding)
    return f"Evidence for {have} of {len(deciding)} {kind}"


@dataclass(frozen=True)
class Pay:
    """The pay a posting states, as the model read it. `quote` is verified elsewhere."""

    minimum: int | None
    maximum: int | None
    currency: str | None
    period: str | None
    quote: str | None


def _monthly(amount: int, period: str) -> int | None:
    if period == "month":
        return amount
    if period == "year":
        return round(amount / 12)
    return None


def salary_check(
    pay: Pay | None, floor_monthly: int | None, currency: str | None
) -> dict[str, Any]:
    """The posting's pay against the track's monthly floor.

    Compared only when both sides name the same currency and the posting's period is a
    month or a year; anything else is `unknown`. With a range the top counts, because
    the range can reach it; a lone minimum below the floor stays `unknown` for the same
    reason.
    """
    result: dict[str, Any] = {
        "status": "unknown",
        "postingMonthly": None,
        "floorMonthly": floor_monthly,
        "currency": currency,
        "quote": pay.quote if pay else None,
    }
    if pay is None or floor_monthly is None or not currency or not pay.currency:
        return result
    if pay.currency.upper() != currency.upper() or pay.period is None:
        return result
    top = pay.maximum if pay.maximum is not None else pay.minimum
    if top is None:
        return result
    monthly = _monthly(top, pay.period)
    if monthly is None:
        return result
    result["postingMonthly"] = monthly
    if monthly >= floor_monthly:
        result["status"] = "meets"
    elif pay.maximum is not None:
        result["status"] = "below"
    return result


def work_mode_check(
    title: str, location: str | None, description: str, wanted: Sequence[str]
) -> dict[str, Any]:
    posting = gates.stated_work_mode(title, location, description)
    if posting is None or not wanted:
        return {"status": "unclear", "posting": posting}
    return {
        "status": "matches" if posting in wanted else "differs",
        "posting": posting,
    }


def region_check(
    title: str,
    location: str | None,
    description: str,
    eligibility: str | None,
    locations: Sequence[str],
) -> dict[str, Any]:
    status, region = gates.region_status(
        title, location, description, eligibility, locations
    )
    return {"status": status, "region": region}
