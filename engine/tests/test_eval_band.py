"""The band, main gap, summary and checks: pure code, no model."""

import pytest

from engine.jobs.eval_band import (
    Judged,
    Pay,
    band_for,
    main_gap,
    region_check,
    salary_check,
    summary,
    work_mode_check,
)


def j(importance: str, status: str, need: str = "x", note: str = "") -> Judged:
    return Judged(need, importance, status, note)


def musts(*statuses: str) -> list[Judged]:
    return [j("must", s, f"need {i}") for i, s in enumerate(statuses)]


@pytest.mark.parametrize(
    ("reqs", "band"),
    [
        (musts("met", "met", "met"), "strong"),
        (musts("met", "partial", "met"), "good"),
        (musts("met", "gap", "met"), "stretch"),
        (musts("met", "unknown", "met"), "stretch"),
        (musts("met", "gap", "gap"), "poor"),
        (musts("gap", "unknown", "met", "met"), "poor"),
        (musts("gap"), "poor"),  # the only must-have is a gap: more than half
        (musts("unknown"), "stretch"),
        (musts("gap", "met"), "stretch"),  # exactly half is not more than half
    ],
)
def test_the_band_follows_the_must_haves(reqs: list[Judged], band: str) -> None:
    assert band_for(reqs) == band


def test_an_important_gap_lowers_strong_to_good() -> None:
    assert band_for([*musts("met", "met"), j("important", "gap")]) == "good"
    assert band_for([*musts("met", "met"), j("important", "met")]) == "strong"
    assert band_for([*musts("met", "met"), j("nice", "gap")]) == "strong"
    assert band_for([*musts("met", "met"), j("important", "unknown")]) == "strong"


def test_without_must_haves_the_important_ones_decide() -> None:
    assert band_for([j("important", "met"), j("nice", "gap")]) == "strong"
    assert band_for([j("important", "gap"), j("important", "met")]) == "stretch"
    assert band_for([j("important", "gap"), j("important", "gap")]) == "poor"
    assert band_for([j("important", "partial"), j("important", "met")]) == "good"


def test_with_only_nice_requirements_they_decide() -> None:
    assert band_for([j("nice", "met")]) == "strong"
    assert band_for([j("nice", "gap")]) == "poor"


def test_no_requirements_has_no_band() -> None:
    with pytest.raises(ValueError, match="no requirements"):
        band_for([])


def test_the_band_never_depends_on_a_requirements_note_or_order() -> None:
    a = [j("must", "met", "a", "n"), j("must", "gap", "b", "m")]
    assert band_for(a) == band_for(list(reversed(a))) == "stretch"


def test_the_main_gap_is_the_first_gap_then_the_first_unknown() -> None:
    reqs = [
        j("must", "met", "a"),
        j("must", "unknown", "b", "no evidence"),
        j("must", "gap", "c", "none"),
        j("must", "gap", "d"),
    ]
    assert main_gap(reqs) == {"need": "c", "status": "gap", "note": "none"}
    assert main_gap(reqs[:2]) == {
        "need": "b",
        "status": "unknown",
        "note": "no evidence",
    }
    assert main_gap([j("must", "met"), j("must", "partial")]) is None


def test_the_main_gap_ignores_requirements_that_do_not_decide() -> None:
    reqs = [j("must", "met", "a"), j("nice", "gap", "b")]
    assert main_gap(reqs) is None


def test_the_summary_counts_met_and_partial_as_evidence() -> None:
    reqs = musts("met", "partial", "gap", "unknown")
    assert summary(reqs) == "Evidence for 2 of 4 must-haves"
    assert (
        summary([j("important", "met")]) == "Evidence for 1 of 1 important requirements"
    )
    assert summary([j("nice", "gap")]) == "Evidence for 0 of 1 requirements"


def pay(
    minimum: int | None = None,
    maximum: int | None = None,
    currency: str | None = "USD",
    period: str | None = "month",
) -> Pay:
    return Pay(minimum, maximum, currency, period, "a quote")


def test_a_monthly_posting_is_compared_with_the_monthly_floor() -> None:
    assert salary_check(pay(1500, 2500), 1000, "USD")["status"] == "meets"
    assert salary_check(pay(500, 900), 1000, "USD")["status"] == "below"
    assert salary_check(pay(500, 900), 1000, "USD")["postingMonthly"] == 900


def test_a_yearly_posting_is_divided_by_twelve() -> None:
    result = salary_check(pay(None, 60_000, period="year"), 1000, "USD")
    assert result["status"] == "meets"
    assert result["postingMonthly"] == 5000
    assert salary_check(pay(None, 9_000, period="year"), 1000, "USD")["status"] == (
        "below"
    )


def test_the_top_of_a_range_counts() -> None:
    assert salary_check(pay(500, 1500), 1000, "USD")["status"] == "meets"


def test_a_lone_minimum_is_never_below() -> None:
    assert salary_check(pay(500), 1000, "USD")["status"] == "unknown"
    assert salary_check(pay(1200), 1000, "USD")["status"] == "meets"


@pytest.mark.parametrize(
    ("posting", "floor", "currency"),
    [
        (None, 1000, "USD"),
        (pay(1500, 2500), None, "USD"),
        (pay(1500, 2500), 1000, None),
        (pay(1500, 2500, currency="EUR"), 1000, "USD"),
        (pay(1500, 2500, currency=None), 1000, "USD"),
        (pay(1500, 2500, period=None), 1000, "USD"),
        (pay(15, 25, period="hour"), 1000, "USD"),
        (pay(None, None), 1000, "USD"),
    ],
)
def test_anything_that_cannot_be_compared_is_unknown(
    posting: Pay | None, floor: int | None, currency: str | None
) -> None:
    result = salary_check(posting, floor, currency)
    assert result["status"] == "unknown"
    assert result["postingMonthly"] is None


def test_the_currency_is_compared_ignoring_case() -> None:
    assert salary_check(pay(1500, 2500, currency="usd"), 1000, "USD")["status"] == (
        "meets"
    )


def test_the_work_mode_check() -> None:
    assert work_mode_check("t", "Remote", "d", ["remote"]) == {
        "status": "matches",
        "posting": "remote",
    }
    assert work_mode_check("t", "Remote", "d", ["onsite"])["status"] == "differs"
    assert work_mode_check("t", None, "A calm job.", ["onsite"]) == {
        "status": "unclear",
        "posting": None,
    }
    assert work_mode_check("t", "Remote", "d", [])["status"] == "unclear"
    assert work_mode_check("t", "Nairobi or Remote", "d", ["onsite"])["status"] == (
        "unclear"
    )


def test_the_region_check() -> None:
    args = ("t", None, "US only.")
    assert region_check(*args, "Kenya", []) == {
        "status": "mismatch",
        "region": "the United States",
    }
    assert region_check(*args, "Can work in the US", [])["status"] == "compatible"
    assert region_check(*args, None, [])["status"] == "unclear"
    assert region_check("t", None, "We hire worldwide.", "Kenya", []) == {
        "status": "none_found",
        "region": None,
    }
