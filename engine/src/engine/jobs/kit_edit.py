"""Change one block of a saved kit document, then check the whole document again.

The person can edit or remove a statement. Nothing is overwritten: the caller saves the
result as the next version. The check runs again over every block from the sources it
already holds, each found again by fact id among the facts of the version's own profile
that are still confirmed or edited. A source whose fact is gone is dropped, so its
block is flagged `no_source`. An entry's heading and a skill's name are read from the
fact as it is now; a skill whose fact is gone is dropped and counted. An edited block
is the person's own words but is held to the same check: an edit that adds a number its
sources do not state is flagged.

Paths are 1-based and are the ones the fact check already names: `summary`,
`paragraphs.N`, `answers.N`, `entries.N` and `entries.N.bullets.M`, plus `skills.N`,
which can only be removed.
"""

import copy
import re
from collections.abc import Sequence
from typing import Any, Literal

from engine.cv.parse import _clean
from engine.errors import ApiError
from engine.jobs.eval_evidence import Fact
from engine.jobs.kit_write import (
    ANSWER_CHARS,
    BULLET_CHARS,
    PARAGRAPH_CHARS,
    SUMMARY_CHARS,
    _Checker,
    _source,
    heading_of,
)

Action = Literal["edit", "remove"]
_ENTRY_KINDS = ("experience", "project", "education")
MAX_PATH_CHARS = 40
MAX_EDIT_CHARS = 2_000

# ASCII digits only and the whole string: no trailing newline, no other scripts' digits.
_PATH = re.compile(
    r"summary|paragraphs\.[1-9][0-9]{0,2}|answers\.[1-9][0-9]{0,2}"
    r"|skills\.[1-9][0-9]{0,2}"
    r"|entries\.[1-9][0-9]{0,2}(?:\.bullets\.[1-9][0-9]{0,2})?"
)
_LIMITS = {
    "summary": SUMMARY_CHARS,
    "bullet": BULLET_CHARS,
    "paragraph": PARAGRAPH_CHARS,
    "answer": ANSWER_CHARS,
}


def _refuse(message: str = "That change is not allowed.") -> ApiError:
    return ApiError(422, "invalid_edit", message)


def _parts(path: str) -> list[str]:
    if len(path) > MAX_PATH_CHARS or not _PATH.fullmatch(path):
        raise _refuse()
    return path.split(".")


def _index(items: Sequence[Any], raw: str) -> int:
    at = int(raw) - 1
    if not 0 <= at < len(items):
        raise _refuse("That statement is not in this document.")
    return at


def _holder(content: dict[str, Any], path: str) -> tuple[Any, Any, str]:
    """The container and key of the block at `path`, and its kind of block."""
    doc = content.get("docType")
    parts = _parts(path)
    head = parts[0]
    if head == "summary" and doc == "cv" and isinstance(content.get("summary"), dict):
        return content, "summary", "summary"
    if head == "paragraphs" and doc in ("letter", "proposal"):
        at = _index(content.get("paragraphs", []), parts[1])
        return content["paragraphs"], at, "paragraph"
    if head == "answers" and doc == "answers":
        at = _index(content.get("answers", []), parts[1])
        return content["answers"], at, "answer"
    if head == "skills" and doc == "cv":
        at = _index(content.get("skills", []), parts[1])
        return content["skills"], at, "skill"
    if head == "entries" and doc == "cv":
        entry_at = _index(content.get("entries", []), parts[1])
        entry = content["entries"][entry_at]
        if len(parts) == 2:
            return content["entries"], entry_at, "entry"
        bullet_at = _index(entry.get("bullets", []), parts[3])
        return entry["bullets"], bullet_at, "bullet"
    raise _refuse("That statement is not in this document.")


def apply_edit(
    content: dict[str, Any], path: str, action: Action, text: str | None
) -> dict[str, Any]:
    """A copy of `content` with one block edited or removed, not yet checked again."""
    changed = copy.deepcopy(content)
    holder, key, kind = _holder(changed, path)
    if action == "remove":
        if kind in ("summary", "answer"):
            raise _refuse("This statement can be edited but not removed.")
        if kind == "paragraph" and len(holder) == 1:
            raise _refuse("A document needs at least one paragraph.")
        del holder[key]
        return changed
    cleaned = _clean(text) if isinstance(text, str) else ""
    if not isinstance(cleaned, str) or not cleaned:
        raise _refuse("Write the statement to save.")
    if kind == "entry":
        raise _refuse("Edit the statements under an entry, not the entry itself.")
    if kind == "skill":
        raise _refuse("A skill can be removed but not edited.")
    if len(cleaned) > _LIMITS[kind]:
        raise _refuse(f"Keep it to {_LIMITS[kind]} characters or fewer.")
    holder[key]["text"] = cleaned
    holder[key]["edited"] = True
    return changed


def _block(
    check: _Checker,
    path: str,
    old: dict[str, Any],
    by_id: dict[str, Fact],
    max_chars: int,
    anchors: set[str] | None = None,
) -> dict[str, Any]:
    labels = [by_id[s["id"]].label for s in old.get("sources", []) if s["id"] in by_id]
    fresh = check.block(path, str(old.get("text", "")), labels, max_chars, anchors)
    fresh.update({k: v for k, v in old.items() if k in ("index", "question")})
    if old.get("edited"):
        fresh["edited"] = True
    return fresh


def recheck(
    content: dict[str, Any], facts: Sequence[Fact], omitted: int = 0
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The document with every block checked again, and its fact check."""
    by_id = {str(f.id): f for f in facts}
    check = _Checker(facts)
    check.omitted = omitted
    out = copy.deepcopy(content)
    edited: list[str] = []

    def note(path: str, block: dict[str, Any]) -> None:
        if block.get("edited"):
            edited.append(path)

    doc = out.get("docType")
    if doc == "cv":
        if isinstance(out.get("summary"), dict):
            out["summary"] = _block(
                check, "summary", out["summary"], by_id, SUMMARY_CHARS
            )
            note("summary", out["summary"])
        for n, entry in enumerate(out.get("entries", []), start=1):
            fact = by_id.get(entry.get("source", {}).get("id", ""))
            anchors = check.anchors(fact) if fact is not None else set()
            if fact is not None and fact.kind in _ENTRY_KINDS:
                # The heading is read from the fact as it is now, never from the copy
                # taken when the kit was written.
                entry["heading"] = heading_of(fact)
                entry["kind"] = fact.kind
                entry["source"] = _source(fact)
            bullets = []
            for m, bullet in enumerate(entry.get("bullets", []), start=1):
                path = f"entries.{n}.bullets.{m}"
                fresh = _block(check, path, bullet, by_id, BULLET_CHARS, anchors)
                note(path, fresh)
                bullets.append(fresh)
            entry["bullets"] = bullets
        # A skill whose fact is gone is dropped and counted, like an unbacked entry.
        skills: list[dict[str, Any]] = []
        for old in out.get("skills", []):
            fact = by_id.get(old.get("id", ""))
            if fact is not None and fact.kind == "skill":
                skills.append({**_source(fact), "name": fact.text})
        check.omitted += len(out.get("skills", [])) - len(skills)
        if "skills" in out:
            out["skills"] = skills
    elif doc in ("letter", "proposal"):
        for n, block in enumerate(out.get("paragraphs", []), start=1):
            out["paragraphs"][n - 1] = _block(
                check, f"paragraphs.{n}", block, by_id, PARAGRAPH_CHARS
            )
            note(f"paragraphs.{n}", out["paragraphs"][n - 1])
    elif doc == "answers":
        for n, block in enumerate(out.get("answers", []), start=1):
            out["answers"][n - 1] = _block(
                check, f"answers.{n}", block, by_id, ANSWER_CHARS
            )
            note(f"answers.{n}", out["answers"][n - 1])
    summary = check.summary()
    summary["edited"] = edited
    return out, summary
