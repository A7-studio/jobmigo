"""The kit fact check: labels and numbers only."""

from engine.jobs.kit_check import check_block, numbers_in, summarise

FACTS = {
    "E1": "Mobile Team Lead at BeatBnk (2025-01 to 2026-05): "
    "cut production bugs by 60%; team velocity up 35%",
    "S1": "Flutter",
    "A1": "Reduced deployment time by 50% across 3 apps and 12,000 users",
}


def test_numbers_are_read_without_commas_and_once() -> None:
    assert numbers_in("12,000 users, 35% faster, 2026, 35 again, 3.5x") == [
        "12000",
        "35%",
        "2026",
        "35",
        "3.5x",
    ]
    assert numbers_in("no figures here") == []
    assert numbers_in("Version v2 and ES6 and k8s") == ["2", "6", "8s"]


def test_a_block_that_cites_a_fact_and_keeps_its_numbers_passes() -> None:
    result = check_block(
        "Cut production bugs by 60% and raised team velocity 35%.",
        ["E1"],
        FACTS,
        max_chars=300,
    )
    assert result.passed
    assert result.sources == ["E1"]


def test_a_block_with_no_valid_source_is_flagged() -> None:
    for sources in ([], ["Z9"], ["", "nope"]):
        result = check_block("Shipped Flutter apps.", sources, FACTS, max_chars=300)
        assert result.flags == ["no_source"], sources
        assert result.sources == []


def test_a_number_the_cited_facts_do_not_state_is_flagged_and_named() -> None:
    result = check_block(
        "Led 8 engineers and cut bugs by 60%.", ["E1"], FACTS, max_chars=300
    )
    assert result.flags == ["unsupported_number"]
    assert result.unsupported == ["8"]


def test_a_derived_figure_is_flagged_until_a_fact_states_it() -> None:
    result = check_block("6+ years of Flutter.", ["S1"], FACTS, max_chars=300)
    assert result.unsupported == ["6"]


def test_a_number_in_another_fact_does_not_count_unless_that_fact_is_cited() -> None:
    assert check_block("50% faster.", ["E1"], FACTS, max_chars=300).unsupported == [
        "50%"
    ]
    assert check_block("50% faster.", ["E1", "A1"], FACTS, max_chars=300).passed


def test_empty_and_too_long_blocks_are_flagged() -> None:
    assert check_block("   ", ["E1"], FACTS, max_chars=10).flags == ["empty"]
    long = check_block("x" * 11, ["E1"], FACTS, max_chars=10)
    assert long.flags == ["too_long"]


def test_sources_are_deduplicated_and_capped() -> None:
    labels = {f"E{i}": "text" for i in range(1, 9)}
    result = check_block("Text.", ["E1", "E1", *labels], labels, max_chars=100)
    assert result.sources == ["E1", "E2", "E3", "E4", "E5"]


def test_the_summary_lists_only_flagged_blocks_by_path() -> None:
    good = check_block("Flutter.", ["S1"], FACTS, max_chars=100)
    bad = check_block("Led 8.", ["E1"], FACTS, max_chars=100)
    summary = summarise([("cv.summary", good), ("cv.bullets.1", bad)])
    assert summary == {
        "blocks": 2,
        "flagged": 1,
        "flags": [
            {"path": "cv.bullets.1", "flags": ["unsupported_number"], "numbers": ["8"]}
        ],
    }


DATED = {
    "E1": "Engineer at Alvin (2020-03-2022-11): grew the team",
    "U1": "Served 10 users",
    "S3": "Q3 launch and Flutter v2",
    "M1": "Reached 10M users and 5% churn",
}


def flagged(text: str, source: str) -> list[str]:
    return check_block(text, [source], DATED, max_chars=300).unsupported


def test_a_magnitude_suffix_is_part_of_the_number() -> None:
    assert flagged("Served 10M users.", "U1") == ["10m"]
    assert flagged("Served 10k users.", "U1") == ["10k"]
    assert flagged("Served 10 million users.", "U1") == ["10m"]
    assert flagged("Served 10 users.", "U1") == []
    assert flagged("Reached 10 million users.", "M1") == []
    assert flagged("Reached 10M users and 5 percent churn.", "M1") == []
    assert flagged("Reached 10 users.", "M1") == ["10"]


def test_a_figure_inside_a_word_is_read() -> None:
    assert flagged("Grew x10.", "S3") == ["10"]
    assert flagged("Grew x10.", "U1") == []
    assert flagged("Grew x9.", "U1") == ["9"]
    assert flagged("Won Q4 and H1.", "S3") == ["4", "1"]
    assert flagged("Shipped the Q3 launch on Flutter v2.", "S3") == []


def test_a_month_in_a_date_is_not_a_figure() -> None:
    assert flagged("Grew 11 times.", "E1") == ["11"]
    assert flagged("Served 03 users.", "E1") == ["03"]
    assert flagged("Led the team since 2020 until 2022.", "E1") == []
    assert flagged("Worked there 2020-03 to 2022-11.", "E1") == []


def test_dates_do_not_swallow_the_next_year() -> None:
    assert numbers_in("(2020-03-2022-11)") == ["2020", "2022"]
    assert numbers_in("2020-03-15 and 2021-12") == ["2020", "2021"]


def test_a_comma_is_a_thousands_separator_only_before_three_digits() -> None:
    assert numbers_in("12,000 and 1,234,567.5") == ["12000", "1234567.5"]
    assert numbers_in("in 2025,2026 and 7,5") == ["2025", "2026", "7", "5"]


def test_a_block_under_an_entry_must_lean_on_the_entry_or_what_belongs_to_it() -> None:
    facts = {"E1": "Role at A (2020-2021): x", "E2": "Role at B", "A1": "Won 3 awards"}
    anchors = {"E1", "A1"}
    own = check_block("Did x.", ["E1"], facts, max_chars=100, anchors=anchors)
    child = check_block("Won 3 awards.", ["A1"], facts, max_chars=100, anchors=anchors)
    other = check_block("Did y.", ["E2"], facts, max_chars=100, anchors=anchors)
    assert own.passed and child.passed
    assert other.flags == ["off_entry"]
    # no anchors means the block is not under an entry
    assert check_block("Did y.", ["E2"], facts, max_chars=100).passed
    # a block with no valid source is only no_source, not also off_entry
    assert check_block("Hi.", [], facts, max_chars=100, anchors=anchors).flags == [
        "no_source"
    ]


USERS = {
    "U1": "Served 10 users",
    "P1": "Cut churn by 35% and lifted retention",
    "B1": "Built 10 B2B apps and 10 M&A deals",
}


def unsupported(text: str, source: str, facts: dict[str, str] = USERS) -> list[str]:
    return check_block(text, [source], facts, max_chars=300).unsupported


def test_every_attached_suffix_and_every_known_magnitude_word_changes_the_number() -> (
    None
):
    for text in (
        "10bn users",
        "10 bn users",
        "10mn users",
        "10 lakh users",
        "10 crore users",
        "10 trillion users",
        "10 mil users",
        "10 Mio users",
        "10 T users",
        "10x users",
        "10th users",
        "$10 users",
        "€ 10 users",
        "10% users",
        "10 percent users",
        "10⁶ users",  # a superscript is read as digits, so it is not 10
    ):
        assert unsupported(text, "U1"), text


def test_a_plain_reworded_number_still_passes() -> None:
    for text in ("Served 10 people.", "10 users, daily.", "Served 10, then 10 more."):
        assert unsupported(text, "U1") == [], text
    assert unsupported("Cut churn 35 percent.", "P1") == []
    assert unsupported("Cut churn 35 per cent.", "P1") == []
    assert unsupported("Cut churn by 35%.", "P1") == []
    assert unsupported("Cut churn by 35.", "P1") == ["35"]


def test_a_unit_hidden_in_a_name_is_read_the_same_on_both_sides() -> None:
    assert unsupported("Built 10 B2B apps.", "B1") == []
    assert unsupported("Closed 10 M&A deals.", "B1") == []
    assert unsupported("Built 10 B2C apps.", "B1") == ["2c"]


def test_ranges_and_decimal_commas_are_checked_digit_by_digit() -> None:
    facts = {"R1": "Worked 3 years at one firm and 5 at another"}
    assert unsupported("3-5 years.", "R1", facts) == []  # stated, see the docstring
    assert unsupported("3,5 years.", "R1", facts) == []
    assert unsupported("4-5 years.", "R1", facts) == ["4"]


def test_a_block_under_an_entry_may_not_cite_another_entry_or_an_education_fact() -> (
    None
):
    facts = {
        "E1": "Role at A: did x",
        "E2": "Role at B: ran 85% coverage",
        "S1": "Flutter",
        "D1": "BSc at Meru",
    }
    anchors = {"E1"}
    extras = {"S1"}

    def flags(sources: list[str], entry: set[str] = anchors) -> list[str]:
        return list(
            check_block(
                "Did x.", sources, facts, max_chars=100, anchors=entry, extras=extras
            ).flags
        )

    assert flags(["E1"]) == []
    assert flags(["E1", "S1"]) == []  # a skill may support a bullet
    assert flags(["E2", "E1"]) == ["off_entry"]  # another job's fact is foreign
    assert flags(["E1", "D1"]) == ["off_entry"]
    assert flags(["S1"]) == ["off_entry"]  # a skill alone is not the entry
    assert flags(["D1"], set()) == ["off_entry"]  # education entries take no bullets
