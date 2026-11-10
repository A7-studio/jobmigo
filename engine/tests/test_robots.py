"""The robots.txt rules: cautious readings, and no way to make matching slow."""

import random
import time

import pytest

from engine.jobs.robots import (
    RobotsTooComplex,
    _match,
    allowed,
    has_undecodable_rule,
    is_robots_body,
    permits,
)


def test_no_rules_allows_and_a_full_block_blocks() -> None:
    assert permits("", "/jobs/1")
    assert permits("User-agent: *\nDisallow:\n", "/jobs/1")
    assert not permits("User-agent: *\nDisallow: /\n", "/jobs/1")


def test_the_longest_match_wins_and_disallow_wins_a_tie() -> None:
    text = "User-agent: *\nDisallow: /jobs/\nAllow: /jobs/public/\n"
    assert not permits(text, "/jobs/secret")
    assert permits(text, "/jobs/public/1")
    tie = "User-agent: *\nAllow: /a\nDisallow: /a\n"
    assert not permits(tie, "/a")


def test_our_group_or_the_star_group_can_block() -> None:
    text = (
        "User-agent: JobmigoBot\nDisallow: /private\n\n"
        "User-agent: *\nDisallow: /scratch\n"
    )
    assert not permits(text, "/private/x")
    assert not permits(text, "/scratch/x")  # cautious: the * group blocks too
    assert permits(text, "/jobs/x")
    assert allowed(text, "SomeoneElse", "/private/x")  # another agent falls back to *


def test_blank_lines_inside_a_record_do_not_end_it() -> None:
    text = "User-agent: *\n\nDisallow: /secret\n\nDisallow: /other\n"
    assert not permits(text, "/secret/1")
    assert not permits(text, "/other/1")


def test_a_leading_byte_order_mark_is_skipped() -> None:
    assert not permits("﻿User-agent: *\nDisallow: /\n", "/x")
    assert is_robots_body("﻿User-agent: *\nDisallow: /\n")


def test_comments_and_case_are_ignored() -> None:
    text = "USER-AGENT: *  # everyone\nDISALLOW: /x # nope\n"
    assert not permits(text, "/x/y")
    assert permits(text, "/y")


def test_wildcards_and_the_end_anchor() -> None:
    text = "User-agent: *\nDisallow: /*.pdf$\nDisallow: /a*b\nDisallow: /price$tag\n"
    assert not permits(text, "/files/cv.pdf")
    assert permits(text, "/files/cv.pdf.html")
    assert not permits(text, "/a-long-b-path")
    assert not permits(text, "/price$tag")  # a mid-pattern "$" is literal


def test_percent_encoded_rules_match_the_decoded_path() -> None:
    assert not permits("User-agent: *\nDisallow: /foo%20bar\n", "/foo bar")


def test_repeated_wildcards_cannot_make_matching_slow() -> None:
    text = "User-agent: *\nDisallow: /" + "*a" * 40 + "*b$\n"
    started = time.perf_counter()
    assert permits(text, "/" + "a" * 2000)
    assert time.perf_counter() - started < 2.0


def test_a_soft_200_html_page_is_not_a_robots_file() -> None:
    assert not is_robots_body("<html><body>Not found</body></html>")
    assert is_robots_body("")
    assert is_robots_body("   \n")
    assert is_robots_body("Sitemap: https://x.example/s.xml")


def test_an_undecodable_rule_makes_the_file_unreadable() -> None:
    assert has_undecodable_rule("User-agent: *\nDisallow: /caf�\n")
    assert has_undecodable_rule("User-agent: *\nDis�allow: /x\n")
    assert not has_undecodable_rule("Sitemap: https://x.example/�\n")
    assert not has_undecodable_rule("# comment �\nUser-agent: *\n")


def _reference_match(pattern: str, path: str) -> int:
    """The original table walk from the source tool: the bit-parallel matcher must agree."""
    from urllib.parse import unquote

    if pattern == "":
        return -1
    pattern = unquote(pattern)
    end_anchor = pattern.endswith("$")
    import re

    pat = re.sub(r"\*{2,}", "*", pattern[:-1] if end_anchor else pattern)
    reach = [True] + [False] * len(pat)
    for j, c in enumerate(pat, 1):
        if c != "*":
            break
        reach[j] = True
    if reach[-1] and not end_anchor:
        return len(pattern)
    for ch in path:
        step = [False] * (len(pat) + 1)
        for j, c in enumerate(pat, 1):
            if c == "*":
                step[j] = step[j - 1] or reach[j]
            elif c == ch:
                step[j] = reach[j - 1]
        reach = step
        if reach[-1] and not end_anchor:
            return len(pattern)
    return len(pattern) if reach[-1] else -1


def test_the_fast_matcher_agrees_with_the_original_table_walk() -> None:
    rng = random.Random(3)
    for _ in range(20_000):
        pattern = "".join(rng.choice("ab/*$%2") for _ in range(rng.randint(0, 8)))
        path = "".join(rng.choice("ab/%2$") for _ in range(rng.randint(0, 10)))
        assert _match(pattern, path) == _reference_match(pattern, path), (pattern, path)


def test_only_the_groups_that_apply_to_us_count_against_the_rule_cap() -> None:
    other = "User-agent: SomeoneElse\n" + "".join(
        f"Disallow: /p{i}\n" for i in range(900)
    )
    assert permits(other + "User-agent: *\nDisallow: /x\n", "/y")
    ours = "User-agent: *\n" + "".join(f"Disallow: /p{i}\n" for i in range(600))
    with pytest.raises(RobotsTooComplex):
        permits(ours, "/y")
    long_rule = "User-agent: *\nDisallow: /" + "a" * 600 + "\n"
    with pytest.raises(RobotsTooComplex):
        permits(long_rule, "/y")


def test_a_record_listing_thousands_of_agents_costs_no_more_than_one() -> None:
    many = "".join(f"User-agent: bot{i}\n" for i in range(8_000))
    text = many + "User-agent: *\n" + "".join(f"Disallow: /p{i}\n" for i in range(400))
    started = time.perf_counter()
    assert not permits(text, "/p7")
    assert permits(text, "/other")
    assert time.perf_counter() - started < 2.0
    # thousands of agents, then thousands of rules: kept for nobody, so nothing grows
    big = many + "".join(f"Disallow: /p{i}\n" for i in range(8_000))
    started = time.perf_counter()
    assert permits(big, "/p7")
    assert time.perf_counter() - started < 2.0
    # a record that names us among many agents still applies to us
    ours = many + "User-agent: JobmigoBot\nDisallow: /secret\n"
    assert not permits(ours, "/secret/1")
