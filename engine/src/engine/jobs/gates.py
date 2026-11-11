"""Code-only rules that remove a job from a track before any model is called.

A gate removes a job only on a clear match. Any doubt passes the job on, because a job
wrongly removed is worse than one extra look. A removal keeps a plain sentence saying
what was found; the job itself is never deleted.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

_LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "ltd",
    "limited",
    "llc",
    "plc",
    "corp",
    "corporation",
    "co",
    "gmbh",
    "ag",
    "sa",
    "bv",
    "srl",
}


@dataclass(frozen=True)
class Removal:
    code: str
    reason: str


def _company_key(name: str) -> str:
    words = re.sub(r"[^\w]+", " ", name.casefold()).split()
    while len(words) > 1 and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def _do_not_apply(company: str, entries: Sequence[str]) -> Removal | None:
    key = _company_key(company)
    if key and any(_company_key(entry) == key for entry in entries):
        return Removal(
            "do_not_apply", f'"{company}" is on your do-not-apply list for this track.'
        )
    return None


# Wording that turns a phrase around ("not fully remote", "no EU only restriction")
# or makes it one item of a list ("the US or Canada only"). Such a phrase proves
# nothing.
_NEGATION = re.compile(
    r"(?:\bnot|\bno|\bnon|n['\u2019]t|\bnever|\bwithout)\W+(?:\w+\W+){0,2}$", re.I
)
_LISTED = re.compile(r"(?:,|/|&|\bor|\band)\s*$", re.I)
# A region phrase turned inside out ("candidates outside the US only").
_OUTSIDE = re.compile(
    r"(?:\boutside|\bexcluding|\bexcept|\bother than|\bnon)[\s-]*(?:of )?(?:the )?$",
    re.I,
)
# A phrase that is taken back or limited right after it ("is not an option", "only
# during onboarding").
_LIMITED = re.compile(
    r"\s*(?:(?:is|are|was|will be|would be)\s*)?(?:not|n['\u2019]t)\b"
    r"|\s*(?:during|until|while|initially|temporarily|at first|for the first)\b",
    re.I,
)


def _stated(pattern: re.Pattern[str], text: str, *, region: bool = False) -> bool:
    """Whether the pattern matches somewhere that clearly says it.

    A match does not count when it is negated before it, taken back or limited after it,
    or, for a region, one item of a list or turned inside out ("outside the US").
    """
    for found in pattern.finditer(text):
        before = text[max(0, found.start() - 24) : found.start()]
        if _NEGATION.search(before) or _LIMITED.match(text, found.end()):
            continue
        if region and (_LISTED.search(before[-8:]) or _OUTSIDE.search(before)):
            continue
        return True
    return False


# Each mode is found only by a phrase that says it about the role. Bare words such as
# "hybrid" or "on-site" are too common in everyday text ("hybrid apps", "on-site
# interviews"), so they count only in the location field or inside these phrases.
_MODE_PHRASES: dict[str, re.Pattern[str]] = {
    "remote": re.compile(
        r"\b(?:fully|100%|completely|entirely)[ -]remote\b"
        r"|\bremote[- ]only\b"
        r"|\bwork(?:ing)? from anywhere\b"
        r"|\bthis (?:is a |role is |position is )remote\b",
        re.I,
    ),
    "hybrid": re.compile(
        r"\bhybrid (?:work|working) (?:model|schedule|setup|arrangement|policy)\b"
        r"|\bhybrid (?:role|position)\b"
        r"|\b\d days? (?:a|per) week (?:in|at) the office\b",
        re.I,
    ),
    "onsite": re.compile(
        r"\b(?:fully |100% )?on[- ]?site (?:role|position|work|only)\b"
        r"|\bin[- ]office (?:role|position)\b"
        r"|\bmust (?:work|be) (?:on[- ]?site|in the office)\b",
        re.I,
    ),
}
_MODE_LOCATION: dict[str, re.Pattern[str]] = {
    "remote": re.compile(r"\bremote\b", re.I),
    "hybrid": re.compile(r"\bhybrid\b", re.I),
    "onsite": re.compile(r"\bon[- ]?site\b", re.I),
}
_MODE_NAME = {"remote": "remote", "hybrid": "hybrid", "onsite": "on-site"}


def _modes_stated(title: str, location: str | None, description: str) -> set[str]:
    found: set[str] = set()
    text = f"{title}\n{description}"
    for mode, pattern in _MODE_PHRASES.items():
        if _stated(pattern, text):
            found.add(mode)
    for mode, pattern in _MODE_LOCATION.items():
        if location and _stated(pattern, location):
            found.add(mode)
    return found


def _work_mode(
    title: str, location: str | None, description: str, wanted: Sequence[str]
) -> Removal | None:
    if not wanted:
        return None
    stated = _modes_stated(title, location, description)
    if len(stated) != 1:
        return None  # nothing clear, or mixed wording
    mode = next(iter(stated))
    if mode in wanted:
        return None
    chosen = ", ".join(_MODE_NAME[item] for item in wanted)
    return Removal(
        "work_mode",
        f"The posting says the role is {_MODE_NAME[mode]}; "
        f"you chose {chosen} for this track.",
    )


# Region names as a posting writes them. "US" must be capitalised: lowercase "us" is a
# pronoun and appears in sentences such as "contact us only by email".
_REGIONS: dict[str, tuple[str, str]] = {
    "the United States": (
        r"(?:(?-i:US|U\.S\.|USA)|united states)",
        r"(?:(?-i:US|U\.S\.|USA)|united states|america)",
    ),
    "the European Union": (
        r"(?:(?-i:EU)|european union|europe)",
        r"(?:(?-i:EU)|european union|europe)",
    ),
    "the United Kingdom": (
        r"(?:(?-i:UK|U\.K\.)|united kingdom|britain)",
        r"(?:(?-i:UK|U\.K\.)|united kingdom|britain|england)",
    ),
    "Canada": (r"canada", r"(?:canada|canadian)"),
}
_REGION_SAYS = [
    (
        name,
        re.compile(
            rf"\b{says}\s+(?:only|residents only|citizens only|candidates only"
            rf"|applicants only)\b"
            rf"|\bmust (?:currently )?(?:reside|live|be (?:located|based|living"
            rf"|residing)) in (?:the )?{says}\b(?!\s*(?:,|/|&|or\b|and\b))",
            re.I,
        ),
        re.compile(rf"\b{excuse}\b", re.I),
    )
    for name, (says, excuse) in _REGIONS.items()
]


def _region_only(
    title: str,
    location: str | None,
    description: str,
    eligibility: str | None,
    locations: Sequence[str],
) -> Removal | None:
    # Without eligibility notes there is nothing to compare with: a place name such as
    # "New York" does not say which country it is in, so the job passes.
    if not (eligibility or "").strip():
        return None
    text = f"{title}\n{location or ''}\n{description}"
    mine = "\n".join([eligibility or "", *locations])
    for name, says, excuse in _REGION_SAYS:
        if _stated(says, text, region=True) and not excuse.search(mine):
            return Removal(
                "region_only",
                f"The posting limits applicants to {name}, and neither your "
                "eligibility notes nor your locations for this track mention it.",
            )
    return None


def run_gates(
    *,
    company: str,
    title: str,
    location: str | None,
    description: str,
    do_not_apply: Sequence[str],
    work_modes: Sequence[str],
    eligibility: str | None,
    locations: Sequence[str],
) -> Removal | None:
    """The first rule that clearly removes the job for this track, or None."""
    return (
        _do_not_apply(company, do_not_apply)
        or _work_mode(title, location, description, work_modes)
        or _region_only(title, location, description, eligibility, locations)
    )
