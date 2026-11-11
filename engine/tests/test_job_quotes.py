"""Quotes: one field, word boundaries, something to read."""

import pytest

from engine.jobs.quotes import fold, locate, occurrences, usable


def test_a_quote_is_found_in_the_field_that_holds_it() -> None:
    fields = ["Flutter Engineer", "Acme Labs", "Remote", "We build apps. Dart skills."]
    assert locate(fields, "Dart skills", min_chars=6) == (3, 15)
    assert locate(fields, "acme labs", min_chars=6) == (1, 0)
    assert locate(fields, "FLUTTER   engineer", min_chars=6) == (0, 0)


def test_a_quote_never_spans_two_fields() -> None:
    fields = ["Flutter Engineer", "Acme", None, "Build apps"]
    assert locate(fields, "Engineer Acme", min_chars=6) is None
    assert locate(fields, "Engineer. Acme", min_chars=6) is None
    assert locate(fields, "Acme Build", min_chars=6) is None


def test_a_quote_must_start_and_end_on_a_word_boundary() -> None:
    assert locate(["mustard skills"], "ard skills", min_chars=6) is None
    assert locate(["mustard skills"], "mustard ski", min_chars=6) is None
    assert locate(["mustard skills"], "mustard skills", min_chars=6) == (0, 0)
    assert locate(["use C++ daily"], "C++", min_chars=3) == (0, 4)


def test_a_quote_needs_a_letter_or_digit_and_a_length() -> None:
    assert locate(["Wait...... what"], "......", min_chars=6) is None
    assert locate(["a b"], "a b", min_chars=6) is None
    assert usable("   ", 1) is None
    assert usable("  Go  ", 2) == "go"


def test_occurrences_counts_every_boundary_match() -> None:
    assert occurrences("dart and dart tools", "dart") == [0, 9]
    assert occurrences("dartboard", "dart") == []


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_empty_fields_are_skipped(text: str) -> None:
    assert locate([text, None], "anything", min_chars=3) is None


def test_fold_collapses_spaces_and_case_but_keeps_line_breaks() -> None:
    assert fold("  A\n\tB  C ") == "a\nb c"
    assert fold("A  \r\n\r\n  B") == "a\nb"
    assert fold("A\tB   C") == "a b c"


def test_a_quote_on_one_line_matches_text_that_wrapped() -> None:
    folded = fold("Strong Dart\nskills required")
    assert occurrences(folded, fold("strong dart skills")) == [0]
    assert locate(["Strong Dart\nskills"], "Strong Dart skills", min_chars=6) == (0, 0)
    assert locate(["Strong Dart skills"], "Strong Dart\nskills", min_chars=6) == (0, 0)
