"""robots.txt rules (RFC 9309), as pure functions: the text goes in, an answer comes out.

Ported from `tools/robots_check.py` in ai-job-search (https://github.com/ai-job-search-dev/
ai-job-search), MIT licence, Copyright (c) 2026 Mads Lorentzen; see THIRD_PARTY_NOTICES.md.
Changes: no fetching (the safe fetcher in `fetch.py` does that), our own agent token, and
typed signatures. The cautious rules are kept:

* the longest matching rule wins, and on equal length Disallow wins;
* a Disallow for our agent token or for `*` blocks the path;
* blank lines inside a record do not end it;
* one leading byte-order mark is skipped;
* a 200 body with no recognised directive (a soft error page), or a User-agent, Allow or
  Disallow line holding U+FFFD (a byte that was not valid UTF-8), is unreadable, and
  unreadable never means permission;
* wildcard matching is a bit-parallel walk, never a regex, and a group that applies to us
  with more than 500 rules, or a rule longer than 512 characters, is unreadable, so a hostile
  file cannot make it slow.
"""

import re
from urllib.parse import unquote

AGENT = "jobmigobot"
_FIELDS = ("user-agent", "allow", "disallow", "sitemap", "crawl-delay", "host")


def is_robots_body(text: str) -> bool:
    """Does this look like a robots.txt?

    A host can answer /robots.txt with 200 and an HTML error page; that parses to zero
    rules, which would read as "allowed". An empty body is a valid allow-all; a non-empty
    body with no recognised directive is treated as unreadable.
    """
    text = text.removeprefix("﻿")
    if not text.strip():
        return True
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip().lower()
        if ":" in line and line.split(":", 1)[0].strip() in _FIELDS:
            return True
    return False


def has_undecodable_rule(text: str) -> bool:
    """Does a User-agent, Allow or Disallow line hold U+FFFD?

    Such a rule was saved in a legacy code page and can never match, so the path would read
    as allowed. The body is unreadable, not permissive. U+FFFD in a comment or another field
    decides nothing.
    """
    for raw in text.removeprefix("﻿").splitlines():
        line = raw.split("#", 1)[0]
        if "�" in line and ":" in line:
            field = line.split(":", 1)[0].replace("�", "").strip().lower()
            if field in ("user-agent", "allow", "disallow"):
                return True
    return False


def _groups(text: str, wanted: set[str]) -> dict[str, list[tuple[bool, str]]]:
    """agent -> [(is_allow, pattern)] for the agents in `wanted` only.

    Blank lines inside a record are tolerated. Only the groups that apply to us are kept,
    and a record that lists thousands of agents costs no more than one that lists one, so a
    hostile file cannot grow memory or time. More than MAX_RULES rules in a group we keep, or
    one rule longer than MAX_PATTERN_CHARS, makes the file unreadable.
    """
    out: dict[str, list[tuple[bool, str]]] = {}
    agents: list[str] = []  # the wanted agents of the current record
    expect = True
    for raw in text.removeprefix("\ufeff").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            if not expect:
                agents, expect = [], True
            name = value.lower()
            if name in wanted and name not in agents:
                agents.append(name)
                out.setdefault(name, [])
        elif field in ("allow", "disallow"):
            expect = False
            for agent in agents:
                if len(value) > MAX_PATTERN_CHARS or len(out[agent]) >= MAX_RULES:
                    raise RobotsTooComplex
                out[agent].append((field == "allow", value))
    return out


class RobotsTooComplex(ValueError):
    """The file has more rules, or longer rules, than we will evaluate: unreadable."""


MAX_RULES = 500
MAX_PATTERN_CHARS = 512


def _match(pattern: str, path: str) -> int:
    """RFC 9309 wildcard match; returns the match length or -1.

    The pattern is percent-decoded to match the already-decoded path. `$` anchors the end
    only at the end of the pattern. The walk is bit-parallel: one integer holds every
    pattern position that matches so far, so the cost is one short integer step per path
    character, not one per (pattern character, path character) pair.
    """
    if pattern == "":
        return -1
    pattern = unquote(pattern)
    end_anchor = pattern.endswith("$")
    pat = re.sub(r"\*{2,}", "*", pattern[:-1] if end_anchor else pattern)
    star = 0
    literal: dict[str, int] = {}
    for j, char in enumerate(pat, 1):
        if char == "*":
            star |= 1 << j
        else:
            literal[char] = literal.get(char, 0) | (1 << j)
    done = 1 << len(pat)
    reach = 1
    reach |= (reach << 1) & star  # a leading "*" matches nothing
    if reach & done and not end_anchor:
        return len(pattern)
    for ch in path:
        step = ((reach << 1) & literal.get(ch, 0)) | (reach & star)
        step |= (step << 1) & star  # a "*" may also match nothing
        reach = step
        if reach & done and not end_anchor:
            return len(pattern)  # a prefix match is enough without "$"
    return len(pattern) if reach & done else -1


def _verdict(rules: list[tuple[bool, str]], path: str) -> tuple[int, bool]:
    """(length of the best match, whether that rule allows); (-1, True) when none matches."""
    best_len, best_allow = -1, True
    for is_allow, pattern in rules:
        length = _match(pattern, path)
        if length > best_len or (length == best_len and length >= 0 and not is_allow):
            best_len, best_allow = length, is_allow  # ties: Disallow wins
    return best_len, best_allow


def allowed(text: str, agent: str, path: str) -> bool:
    """Is `path` allowed for `agent`: its own group, else `*`, else no rules."""
    groups = _groups(text, {agent.lower(), "*"})
    rules = groups.get(agent.lower()) or groups.get("*") or []
    length, allow = _verdict(rules, path)
    return True if length < 0 else allow


def permits(text: str, path: str) -> bool:
    """May we read `path`? Blocked if our agent group or `*` says no (the cautious reading)."""
    groups = _groups(text, {AGENT, "*"})
    for agent in (AGENT, "*"):
        length, allow = _verdict(groups.get(agent) or [], path)
        if length >= 0 and not allow:
            return False
    return True
