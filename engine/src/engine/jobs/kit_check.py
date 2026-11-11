"""The fact check for a written block: a cited fact, and the same numbers.

This reads no meaning from prose. A block carries the labels of the confirmed facts it
is built from (the labels `eval_evidence` hands the model). The check is only:

* the block cites at least one label that exists (otherwise `no_source`);
* every number written in the block also appears, written the same way, in at least
  one cited fact (otherwise `unsupported_number`, naming the number);
* the block is not empty and not over its length cap;
* when the block sits under an entry, it cites the entry's own fact or a fact that
  belongs to it, plus at most skills (otherwise `off_entry`).

What counts as a number: any run of digits, wherever it sits (so `Q3` and `x10` are the
numbers 3 and 10), with thousands commas removed. What is attached to the digits is part
of the number: a currency sign before it, and letters or a percent sign after it, so
`$10`, `10bn`, `10x`, `5th` and `35%` are each different from a plain `10`. A magnitude
or unit written as a separate word after a space (`10 million`, `35 percent`, `10 lakh`)
is part of the number only if it is in a finite list (`_UNIT`); a magnitude word that is
not in the list is not seen. In a date such as `2020-03` only the year counts, so a
month never supports a figure. Full-width digits and superscripts are folded to plain
digits first.

How it is limited, so nobody over-trusts it:

* A range or a decimal comma is read digit by digit: "3-5 years" and "3,5 years" pass
  when the cited facts state a 3 and a 5 separately.
* A figure the model worked out itself, such as "6+ years", is flagged unless a cited
  fact states it.
* Letters attached to digits are read literally, so a name such as `B2B` gives the
  number `2b` on both sides, and `3years` is not `3`.
* Numbers spelled out in words, names, tools, employers, titles, and whether the wording
  means what the fact means, are not checked. The person reads the text themselves.
"""

import re
import unicodedata
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

Flag = Literal["no_source", "unsupported_number", "empty", "too_long", "off_entry"]

MAX_SOURCES = 5
# A date's month and day are not figures: only its year is kept. A day is read only when
# no digit follows it, so "2020-03-2022-11" is two dates, not "2020-03-20" and "22-11".
_DATE = re.compile(
    r"(?<!\d)(\d{4})-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01])(?!\d))?(?!\d)"
)
# A currency sign, digits (with thousands commas or decimals), then what is attached
# to them: letters or a percent sign (`10bn`, `10x`, `35%`), or else the next word.
_NUMBER = re.compile(
    r"(?P<cur>[$\u20ac\u00a3\u00a5\u20b9]\s?)?"
    r"(?P<n>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:(?P<att>[a-z]+(?![a-z0-9&])|%)"
    r"|\s+(?P<word>per\s?cent|[a-z]+)(?![a-z0-9&]))?",
    re.IGNORECASE,
)
# A word after a space changes the number only when it is one of these. The list is
# finite: a magnitude word that is not here is not seen. Letters attached to the digits
# are always kept, so `10bn` is never `10`.
_UNIT = {
    "k": "k",
    "thousand": "k",
    "m": "m",
    "mn": "m",
    "mil": "m",
    "mio": "m",
    "million": "m",
    "b": "b",
    "bn": "b",
    "billion": "b",
    "t": "t",
    "tn": "t",
    "trillion": "t",
    "lakh": "lakh",
    "lac": "lakh",
    "crore": "crore",
    "cr": "crore",
    "percent": "%",
    "pct": "%",
    "per cent": "%",
    "percentage": "%",
}
_ATTACHED = {"percent": "%", "pct": "%", "thousand": "k", "million": "m"}


def numbers_in(text: str) -> list[str]:
    """The numbers in `text`, as written, once each, in order.

    A number is its digits plus a currency sign before it and a magnitude, unit or
    percent after it, so `$10`, `10M`, `10 million`, `10bn`, `10x` and `35%` are all
    different from a plain `10`. Text is first folded to plain digits (full-width digits
    and superscripts become ordinary digits).
    """
    seen: dict[str, None] = {}
    folded = unicodedata.normalize("NFKC", text)
    for found in _NUMBER.finditer(_DATE.sub(r"\1", folded)):
        marker = ""
        if found.group("att"):
            att = found.group("att").lower()
            marker = _ATTACHED.get(att, _UNIT.get(att, att))
        elif found.group("word"):
            word = re.sub(r"\s+", " ", found.group("word").lower())
            marker = _UNIT.get(word, "")
        currency = (found.group("cur") or "").strip()
        digits = found.group("n").replace(",", "")
        seen.setdefault(f"{currency}{digits}{marker}", None)
    return list(seen)


@dataclass(frozen=True)
class BlockCheck:
    """The outcome for one block: no flags means it passed."""

    sources: list[str]
    flags: list[Flag] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.flags


def check_block(
    text: str,
    sources: Iterable[str],
    facts: Mapping[str, str],
    *,
    max_chars: int,
    anchors: Collection[str] | None = None,
    extras: Collection[str] = (),
) -> BlockCheck:
    """Check one block against the confirmed facts, keyed by label.

    `anchors` are the labels a block under an entry may lean on (the entry's own fact
    and the facts that belong to it) and `extras` are facts that may support it without
    belonging to it (skills). The block must cite at least one anchor and nothing else
    but anchors and extras, or it is `off_entry`.
    """
    valid: list[str] = []
    for label in sources:
        if label in facts and label not in valid:
            valid.append(label)
        if len(valid) == MAX_SOURCES:
            break
    flags: list[Flag] = []
    body = text.strip()
    if not body:
        flags.append("empty")
    elif len(body) > max_chars:
        flags.append("too_long")
    if not valid:
        flags.append("no_source")
    elif anchors is not None and (
        not any(label in anchors for label in valid)
        or any(label not in anchors and label not in extras for label in valid)
    ):
        flags.append("off_entry")
    unsupported: list[str] = []
    if valid and body:
        cited = {n for label in valid for n in numbers_in(facts[label])}
        unsupported = [n for n in numbers_in(body) if n not in cited]
        if unsupported:
            flags.append("unsupported_number")
    return BlockCheck(sources=valid, flags=flags, unsupported=unsupported)


def summarise(checks: Sequence[tuple[str, BlockCheck]]) -> dict[str, object]:
    """A stored summary: blocks, how many are flagged, and each flag by block path."""
    flagged = [(path, c) for path, c in checks if not c.passed]
    return {
        "blocks": len(checks),
        "flagged": len(flagged),
        "flags": [
            {"path": path, "flags": list(c.flags), "numbers": list(c.unsupported)}
            for path, c in flagged
        ],
    }
