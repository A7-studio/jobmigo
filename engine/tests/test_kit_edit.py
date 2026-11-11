"""Editing or removing one statement, then checking the whole document again."""

import copy
import uuid
from typing import Any

import pytest

from engine.errors import ApiError
from engine.jobs.eval_evidence import Fact
from engine.jobs.kit_edit import apply_edit, recheck
from engine.jobs.kit_write import (
    AnswersOut,
    CvOut,
    LetterOut,
    verify_answers,
    verify_cv,
    verify_paragraphs,
)

E1 = Fact(
    "E1", "experience", uuid.uuid4(), "Lead at BeatBnk (2025-2026): cut bugs by 60%"
)
E2 = Fact(
    "E2", "experience", uuid.uuid4(), "Engineer at Alvin (2022-2024): 85% coverage"
)
A1 = Fact("A1", "achievement", uuid.uuid4(), "Won 3 awards", E1.id)
S1 = Fact("S1", "skill", uuid.uuid4(), "Flutter")
D1 = Fact("D1", "education", uuid.uuid4(), "BSc at Meru")
FACTS = [E1, E2, A1, S1, D1]


def cv_content() -> tuple[dict[str, Any], dict[str, Any]]:
    out = CvOut.model_validate(
        {
            "summary": {"text": "Flutter lead.", "sources": ["E1", "S1"]},
            "entries": [
                {
                    "fact": "E1",
                    "bullets": [
                        {"text": "Cut bugs by 60%.", "sources": ["E1"]},
                        {"text": "Won 3 awards.", "sources": ["A1"]},
                        {"text": "Led 12 people.", "sources": ["E1"]},
                    ],
                },
                {
                    "fact": "E2",
                    "bullets": [{"text": "85% coverage.", "sources": ["E2"]}],
                },
            ],
            "skills": ["S1"],
        }
    )
    return verify_cv(out, FACTS)


def letter_content() -> dict[str, Any]:
    out = LetterOut.model_validate(
        {
            "paragraphs": [
                {"text": "I lead Flutter.", "sources": ["E1"]},
                {"text": "I cut bugs by 60%.", "sources": ["E1"]},
            ]
        }
    )
    return verify_paragraphs(out, FACTS, "letter")[0]


def answers_content() -> dict[str, Any]:
    out = AnswersOut.model_validate(
        {"answers": [{"index": 1, "text": "Yes, Flutter.", "sources": ["S1"]}]}
    )
    return verify_answers(out, ["Flutter?"], FACTS)[0]


def test_editing_a_bullet_saves_the_text_marks_it_and_checks_it_again() -> None:
    content, check = cv_content()
    assert check["flags"][0]["path"] == "entries.1.bullets.3"  # "12" is unsupported
    changed = apply_edit(content, "entries.1.bullets.3", "edit", "Led the team.")
    fixed, summary = recheck(changed, FACTS, check["omitted"])
    bullet = fixed["entries"][0]["bullets"][2]
    assert (bullet["text"], bullet["flags"], bullet["edited"]) == (
        "Led the team.",
        [],
        True,
    )
    assert summary["flagged"] == 0
    assert summary["edited"] == ["entries.1.bullets.3"]


def test_an_edit_that_adds_an_untraceable_number_is_flagged_like_any_other() -> None:
    content, _ = cv_content()
    changed = apply_edit(content, "entries.1.bullets.1", "edit", "Cut bugs by 90%.")
    again, summary = recheck(changed, FACTS)
    bullet = again["entries"][0]["bullets"][0]
    assert bullet["flags"] == ["unsupported_number"]
    assert bullet["numbers"] == ["90%"]
    assert summary["flags"][0]["path"] == "entries.1.bullets.1"


def test_removing_a_bullet_renumbers_the_paths() -> None:
    content, check = cv_content()
    changed = apply_edit(content, "entries.1.bullets.1", "remove", None)
    again, summary = recheck(changed, FACTS, check["omitted"])
    assert [b["text"] for b in again["entries"][0]["bullets"]] == [
        "Won 3 awards.",
        "Led 12 people.",
    ]
    assert summary["flags"][0]["path"] == "entries.1.bullets.2"  # was bullets.3
    assert summary["blocks"] == 4


def test_removing_an_entry_and_a_paragraph() -> None:
    content, _ = cv_content()
    gone = apply_edit(content, "entries.2", "remove", None)
    assert [e["source"]["label"] for e in gone["entries"]] == ["E1"]
    letter = apply_edit(letter_content(), "paragraphs.1", "remove", None)
    assert [p["text"] for p in letter["paragraphs"]] == ["I cut bugs by 60%."]


def test_the_input_is_never_changed() -> None:
    content, _ = cv_content()
    before = copy.deepcopy(content)
    apply_edit(content, "entries.1.bullets.1", "edit", "Changed.")
    apply_edit(content, "entries.1", "remove", None)
    assert content == before


@pytest.mark.parametrize(
    ("builder", "path", "action", "text"),
    [
        (cv_content, "summary", "remove", None),
        (cv_content, "entries.1", "edit", "Renamed"),
        (cv_content, "entries.9", "remove", None),
        (cv_content, "entries.1.bullets.9", "remove", None),
        (cv_content, "entries.0", "remove", None),
        (cv_content, "entries.1.bullets", "remove", None),
        (cv_content, "entries.1.bullets.1", "edit", ""),
        (cv_content, "entries.1.bullets.1", "edit", "   "),
        (cv_content, "entries.1.bullets.1", "edit", None),
        (cv_content, "entries.1.bullets.1", "edit", "x" * 301),
        (cv_content, "paragraphs.1", "remove", None),  # wrong kind of document
        (cv_content, "summary.1", "edit", "x"),
        (cv_content, "", "edit", "x"),
        (cv_content, "../x", "edit", "x"),
        (cv_content, "entries.1.bullets.1 ", "edit", "x"),
        (cv_content, "x" * 80, "edit", "x"),
    ],
)
def test_a_bad_change_is_refused(
    builder: Any, path: str, action: str, text: str | None
) -> None:
    content = builder()
    content = content[0] if isinstance(content, tuple) else content
    with pytest.raises(ApiError) as caught:
        apply_edit(content, path, action, text)  # type: ignore[arg-type]
    assert (caught.value.status, caught.value.code) == (422, "invalid_edit")


def test_the_last_paragraph_and_any_answer_cannot_be_removed() -> None:
    one = apply_edit(letter_content(), "paragraphs.1", "remove", None)
    with pytest.raises(ApiError):
        apply_edit(one, "paragraphs.1", "remove", None)
    with pytest.raises(ApiError):
        apply_edit(answers_content(), "answers.1", "remove", None)
    changed = apply_edit(answers_content(), "answers.1", "edit", "Yes, daily.")
    assert changed["answers"][0]["text"] == "Yes, daily."
    assert changed["answers"][0]["question"] == "Flutter?"


def test_a_source_whose_fact_is_gone_flags_its_block() -> None:
    content, _ = cv_content()
    without_e2 = [f for f in FACTS if f is not E2]
    again, summary = recheck(content, without_e2)
    bullet = again["entries"][1]["bullets"][0]
    assert bullet["flags"] == ["no_source"]
    assert bullet["sources"] == []
    assert summary["flags"][-1]["path"] == "entries.2.bullets.1"


def test_sources_are_found_again_by_id_even_if_the_labels_moved() -> None:
    content, _ = cv_content()
    moved = [
        Fact("E1", E2.kind, E2.id, E2.text),
        Fact("E2", E1.kind, E1.id, E1.text),
        A1,
        S1,
        D1,
    ]
    again, _ = recheck(content, moved)
    assert again["entries"][0]["source"]["label"] == "E1"  # the stored source is kept
    # the first bullet cited the fact with E1's id, now labelled E2, and still passes
    assert again["entries"][0]["bullets"][0]["flags"] == []
    assert again["entries"][0]["bullets"][0]["sources"][0]["id"] == str(E1.id)


def test_a_block_edited_before_stays_marked_and_the_omitted_count_is_kept() -> None:
    content, _ = cv_content()
    once = apply_edit(content, "entries.1.bullets.1", "edit", "Cut bugs a lot.")
    first, summary = recheck(once, FACTS, 4)
    assert summary["omitted"] == 4
    twice = apply_edit(first, "entries.1.bullets.2", "edit", "Won awards.")
    second, summary2 = recheck(twice, FACTS, summary["omitted"])
    assert summary2["edited"] == ["entries.1.bullets.1", "entries.1.bullets.2"]
    assert second["entries"][0]["bullets"][0]["edited"] is True


def test_answers_keep_their_question_and_index() -> None:
    changed = apply_edit(answers_content(), "answers.1", "edit", "Yes, daily.")
    again, summary = recheck(changed, FACTS)
    assert (again["answers"][0]["index"], again["answers"][0]["question"]) == (
        1,
        "Flutter?",
    )
    assert summary["edited"] == ["answers.1"]


@pytest.mark.parametrize(
    "content", [{"docType": "cv"}, {"docType": "letter"}, {"docType": "answers"}, {}]
)
def test_stored_content_with_missing_parts_is_refused_or_checked_not_a_crash(
    content: dict[str, Any],
) -> None:
    for path in (
        "summary",
        "entries.1",
        "entries.1.bullets.1",
        "paragraphs.1",
        "answers.1",
    ):
        with pytest.raises(ApiError) as caught:
            apply_edit(content, path, "edit", "x")
        assert caught.value.code == "invalid_edit"
    checked, summary = recheck(content, FACTS)
    assert checked == content
    assert summary["blocks"] == 0


@pytest.mark.parametrize(
    "path",
    [
        "entries.1.bullets.1\n",
        "summary\n",
        "entries." + chr(0x661) + ".bullets.1",  # an Arabic-Indic digit
        "paragraphs." + chr(0xFF11),  # a full-width digit
        " summary",
    ],
)
def test_a_path_must_be_exactly_a_path_in_ascii(path: str) -> None:
    content, _ = cv_content()
    with pytest.raises(ApiError) as caught:
        apply_edit(content, path, "edit", "x")
    assert caught.value.code == "invalid_edit"


def test_a_skill_whose_fact_is_gone_is_dropped_and_counted_by_the_recheck() -> None:
    content, _ = cv_content()
    assert [s["label"] for s in content["skills"]] == ["S1"]
    without_skill = [f for f in FACTS if f is not S1]
    again, summary = recheck(content, without_skill, 1)
    assert again["skills"] == []
    assert summary["omitted"] == 2  # the earlier one and this skill


def test_a_skill_can_be_removed_but_not_edited() -> None:
    content, _ = cv_content()
    gone = apply_edit(content, "skills.1", "remove", None)
    assert gone["skills"] == []
    with pytest.raises(ApiError):
        apply_edit(content, "skills.1", "edit", "Dart")
    with pytest.raises(ApiError):
        apply_edit(content, "skills.2", "remove", None)
    with pytest.raises(ApiError):
        apply_edit(gone, "skills.1", "remove", None)
    again, _ = recheck(gone, FACTS)
    assert again["skills"] == []
