"""Clean an untrusted job posting and count what looked wrong.

Ported from `tools/posting_guard.py` and `page_decode.py`'s companion rules in
ai-job-search (https://github.com/ai-job-search-dev/ai-job-search), MIT licence,
Copyright (c) 2026 Mads Lorentzen; see THIRD_PARTY_NOTICES.md. Changes: library
only (no command line or file handling), the instruction patterns that named another
tool's files or ordinary shell words are removed (they would flag everyday engineering
postings), the verdict text is dropped, and `clean_posting` keeps counts, never excerpts.

A posting is third-party text that later features read next to the user's profile.
Hidden HTML, invisible and Unicode tag characters are removed from the text; instruction
shaped lines are counted, never removed. This advises; it never blocks.
"""

import html
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

EXCERPT = 120
LINE_MAX = 200

ZERO_WIDTH = "​‌‍⁠⁡⁢⁣⁤"
BIDI = "‎‏‪‫‬‭‮⁦⁧⁨⁩"
BIDI_TAMPER = "‭‮⁦⁧⁨⁩"  # overrides and isolates
FORMAT = "­  "  # soft hyphen, line/paragraph separators
BOM = "﻿"
# U+E0000-U+E007F: the Unicode "tags" block, one invisible code point per ASCII
# character. A payload written in it survives copy-paste, never renders, and
# is decoded by a model as if it were the ASCII it mirrors ("ASCII smuggling");
# a single one inside "ignore" also splits the word past every instruction
# pattern.
TAG_CHARS = "".join(chr(c) for c in range(0xE0000, 0xE0080))
INVISIBLE = ZERO_WIDTH + BIDI + FORMAT + BOM + TAG_CHARS
TAG_RUN = re.compile("[\U000e0000-\U000e007f]+")
# The one legitimate use of tag characters: the England, Scotland and Wales
# flags (black flag, tag letters gbeng/gbsct/gbwls, cancel tag). Matched in
# full and left intact; a payload inside a well-formed tag sequence, extra
# tags after a valid flag, or a non-RGI subdivision still count and alarm.
RGI_TAG_FLAG = re.compile(
    "\U0001f3f4\U000e0067\U000e0062(?:\U000e0065\U000e006e\U000e0067"
    "|\U000e0073\U000e0063\U000e0074|\U000e0077\U000e006c\U000e0073)\U000e007f"
)
# Variation selectors (U+FE00-FE0F, U+E0100-E01EF) pick a glyph variant and
# render as nothing on their own; a run of them carries one byte each. A lone
# one (the VS16 in ❤️) is encoding noise; a run is a payload.
VARIATION = re.compile("[︀-️\U000e0100-\U000e01ef]")
VARIATION_RUN = re.compile("[︀-️\U000e0100-\U000e01ef]{2,}")

HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none"
    r"|visibility\s*:\s*hidden"
    r"|opacity\s*:\s*0(?![.\d]*[1-9])"
    r"|font-size\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?(?![\d.])"
    r"|color\s*:\s*transparent"
    r"|clip\s*:\s*rect\(\s*0"
    r"|clip-path\s*:\s*inset\(\s*100%"
    r"|(?:left|top|text-indent)\s*:\s*-\d{4,}px",
    re.I,
)
# The HTML reader below is a single pass: every character is looked at a bounded number of
# times, whatever the input. There is no regex that can scan to the end of the input per
# opener, so a hostile page cannot make it slow, and a tag of any length is read as a tag.
# Anything unterminated (a tag, comment, declaration or script) hides the rest of the input,
# as a browser reads it, so hidden content can never be revealed by leaving something open.
_WS = "[ \\t\\n\\f\\r]"
_NAME_REST = re.compile(rf"[^{_WS[1:-1]}/>]*")
_SKIP = re.compile(rf"[{_WS[1:-1]}/]*")
_SPACE = re.compile(rf"{_WS}*")
_ATTR_NAME = re.compile(rf"[^{_WS[1:-1]}/>=]*")
_UNQUOTED = re.compile(rf"[^{_WS[1:-1]}>]*")
_NAME = re.compile(r"(/?)([a-zA-Z][\w:-]*)")
_OPEN = re.compile(r"<!--|<!|<\?|<(script|style|noscript|svg|template)\b", re.I)
_CLOSERS = {
    name: re.compile(rf"</{name}\s*>", re.I)
    for name in ("script", "style", "noscript", "svg", "template")
}
VOID = {
    "br",
    "img",
    "input",
    "meta",
    "link",
    "hr",
    "wbr",
    "source",
    "area",
    "base",
    "col",
    "embed",
    "param",
    "track",
}
BLOCK = {
    "p",
    "div",
    "li",
    "ul",
    "ol",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "tr",
    "br",
    "section",
    "article",
    "header",
    "footer",
    "table",
    "thead",
    "tbody",
    "blockquote",
    "pre",
    "dd",
    "dt",
    "dl",
    "nav",
    "main",
    "aside",
    "figure",
    "form",
    "fieldset",
    "legend",
    "address",
    "hr",
    "td",
    "th",
    "option",
}
IMPLIED_END = {
    "p",
    "li",
    "dd",
    "dt",
    "tr",
    "td",
    "th",
    "option",
}  # an open one is closed by a sibling
CLOSES_P = BLOCK - {"br"}  # an open <p> is closed by any block-level opener
HTML_HINT = re.compile(r"<\s*(html|body|div|p)\b", re.I)

URL = re.compile(r"https?://[^\s<>\"')\]]+")
INSTRUCTION_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\bignore (all|any|the|previous|prior|above|earlier)\b",
        # The same instruction with its other two verbs. These take an explicit
        # object ("previous instructions"), because "forget the" and "disregard
        # the" are ordinary prose where "ignore the" already is not.
        r"\b(disregard|forget)( all| any| the| your| my)? (previous|prior|above|earlier|preceding|initial|original|system) (instructions?|prompts?)\b",
        r"\byou are (?:an?|the) (?:ai(?![\w-])|ai (?:assistant|agent|model|language model)|assistant|llm|language model)\b",
        r"\bsystem prompt\b",
        # "do not tell the user", "never inform the user": the verb straight onto
        # "the user" (not "the user's"), with the typographic apostrophe most web
        # text uses. Kept narrow on purpose: "never disclose user data" and "do
        # not tell users about unreleased features" are everyday privacy and
        # support prose.
        r"\b(do not|don['\u2019]?t|never) (tell|inform) the user\b(?!['\u2019]s)",
        # "do not reveal these instructions to the user", "never mention this to
        # the user": a demonstrative object, then "to the user" within a clause.
        r"\b(do not|don['\u2019]?t|never) (mention|reveal|disclose) (this|these|that|it|any of this|the (above|following|previous))\b[^.\n]{0,30}\bto the user\b",
        r"\b(run|execute) the following (command|commands|script|code|shell|instruction|instructions|steps)\b",
        # "As an AI" flags by default. Exempt only a job-title noun within a few words of "AI", the way AI
        # job ads introduce the role ("As an AI Engineer", "as an AI/ML Researcher", "As an AI Product Manager").
        r"\bas an ai(?![\w-])(?![\s/&]+(?:[\w&/-]+\s+){0,3}?(?:engineer|developer|researcher|scientist|architect|specialist|lead|consultant|manager|analyst|intern|trainer|expert|strategist|designer|tester|owner|programmer)s?\b)",
        r"^\s*(assistant|system|user)\s*:",
        r"<\|",
        r"\[INST\]",
        r"###\s*(system|instruction)",
        r"\btool_use\b|\bfunction_call\b",
    )
]
WORD = re.compile(r"\w+", re.UNICODE)
LATIN = re.compile(r"[A-Za-z]")
CONFUSABLE = re.compile(r"[Ѐ-ӿͰ-Ͽ]")


def _fold(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\xa0\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: str) -> tuple[str, dict[str, Any]]:
    """Remove invisible characters.

    Returns (text, {"invisible_chars": {category: count}, "invisible_flagged": n,
    "invisible_text": [decoded, ...]}) where the flagged count covers a
    zero-width or BOM character between two letters (splitting a word to dodge
    a scan) and any bidi override or isolate. A BOM at offset 0, emoji joiners,
    RTL marks, soft hyphens, emoji flag tags and a lone variation selector are
    counted but not flagged: they are encoding noise, not tampering. Tag
    character runs and variation selector runs are decoded into
    invisible_text instead, since what they spell is the payload.
    """
    counts = {}
    flagged = 0
    for key, chars in (
        ("zero_width", ZERO_WIDTH),
        ("bidi", BIDI),
        ("format", FORMAT),
        ("bom", BOM),
    ):
        n = sum(text.count(c) for c in chars)
        if n:
            counts[key] = n
    flags = RGI_TAG_FLAG.findall(text)
    unflagged = RGI_TAG_FLAG.sub("", text)  # the text minus its legitimate flags
    tags = sum(1 for ch in unflagged if "\U000e0000" <= ch <= "\U000e007f")
    if tags:
        counts["tag"] = tags
    variation = len(VARIATION.findall(text))
    if variation:
        counts["variation"] = variation
    for i, ch in enumerate(text):
        if ch in BIDI_TAMPER:
            flagged += 1
        elif ch in ZERO_WIDTH or ch == BOM:
            before = text[i - 1] if i else ""
            after = text[i + 1] if i + 1 < len(text) else ""
            if before.isalpha() and after.isalpha():
                flagged += 1
    invisible_text = []
    for run in TAG_RUN.findall(unflagged):
        decoded = "".join(
            chr(ord(c) - 0xE0000) for c in run if 0x20 <= ord(c) - 0xE0000 < 0x7F
        ).strip()
        if decoded:
            invisible_text.append(decoded[:LINE_MAX])
    for run in VARIATION_RUN.findall(text):
        data = bytes(
            ord(c) - 0xFE00 if ord(c) <= 0xFE0F else ord(c) - 0xE0100 + 16 for c in run
        )
        decoded = "".join(
            c for c in data.decode("utf-8", errors="replace") if c.isprintable()
        ).strip()
        if decoded:
            invisible_text.append(decoded[:LINE_MAX])
    text = VARIATION.sub("", text)
    if flags:
        # Strip around the flags so the visible emoji survive intact.
        strip = {ord(c): None for c in INVISIBLE}
        pieces, last = [], 0
        for m in RGI_TAG_FLAG.finditer(text):
            pieces.append(text[last : m.start()].translate(strip))
            pieces.append(m.group(0))
            last = m.end()
        pieces.append(text[last:].translate(strip))
        text = "".join(pieces)
    else:
        text = text.translate({ord(c): None for c in INVISIBLE})
    return _fold(text), {
        "invisible_chars": counts,
        "invisible_flagged": flagged,
        "invisible_text": invisible_text,
    }


def _strip_css_comments(css: str) -> str:
    """Remove /* ... */ in one pass; an unterminated one runs to the end, as in a browser."""
    out: list[str] = []
    pos = 0
    while True:
        start = css.find("/*", pos)
        if start < 0:
            break
        out.append(css[pos:start])
        close = css.find("*/", start + 2)
        if close < 0:
            return "".join(out)
        pos = close + 2
    out.append(css[pos:])
    return "".join(out)


# A box collapsed to nothing with its overflow clipped hides its content as
# surely as display:none. Either half alone is everyday layout CSS (overflow:
# hidden is on most cards; height:0 is a spacer), so both must be present.
COLLAPSED_BOX = re.compile(
    r"\b(?:max-)?(?:height|width)\s*:\s*0(?:\.0+)?(?:px|em|rem|%|pt)?(?![\d.])", re.I
)
CLIPPED = re.compile(r"\boverflow(?:-[xy])?\s*:\s*hidden\b", re.I)


def _style(attrs: dict[str, str]) -> str:
    """The style attribute as a browser reads it: entities decoded, CSS comments gone.

    A browser decodes `display&#58;none` before parsing the CSS and ignores
    `/**/` inside a declaration, so both hid the content while the regex saw
    neither. Normalise before matching.
    """
    return _strip_css_comments(html.unescape(attrs.get("style", "")))


def _is_hidden(attrs: dict[str, str]) -> bool:
    if "hidden" in attrs or attrs.get("aria-hidden", "").strip().lower() == "true":
        return True
    style = _style(attrs)
    if HIDDEN_STYLE.search(style):
        return True
    return bool(COLLAPSED_BOX.search(style) and CLIPPED.search(style))


def _after(pattern: re.Pattern[str], markup: str, i: int) -> int:
    """Where a run of characters matched at `i` ends (these patterns can match nothing)."""
    found = pattern.match(markup, i)
    return found.end() if found else i


_KEPT_ATTRS = ("hidden", "aria-hidden", "style")


def _scan_tag(markup: str, start: int) -> tuple[int, dict[str, str]]:
    """Read one start tag; return (index just after its ">", the attributes we look at).

    `start` is where the tag name begins (or just after it). This follows the HTML
    tokenizer's start-tag states, so the tag ends where a browser ends it and attribute
    values are the ones a browser sees: the name runs to whitespace, "/" or ">" (so it may
    hold "=" or a quote); the first character of an attribute name is always part of the
    name (even "="); a quote opens a value only after "=" (and spaces); an unquoted value
    runs to whitespace or ">" (quotes inside it are ordinary); the first copy of a repeated
    attribute wins. Only `hidden`, `aria-hidden` and `style` are kept. One pass: each
    character is read a bounded number of times. The index is -1 when the tag is never
    closed.
    """
    size = len(markup)
    attrs: dict[str, str] = {}
    i = _after(_NAME_REST, markup, start)
    while True:
        i = _after(_SKIP, markup, i)  # before attribute name
        if i >= size:
            return -1, attrs
        if markup[i] == ">":
            return i + 1, attrs
        name_start = i
        i = _after(_ATTR_NAME, markup, i + 1)
        name = markup[name_start:i].lower()
        i = _after(_SPACE, markup, i)  # after attribute name
        if i >= size:
            return -1, attrs
        value = ""
        if markup[i] == "=":
            i = _after(_SPACE, markup, i + 1)
            if i >= size:
                return -1, attrs
            quote = markup[i]
            if quote in "\"'":
                close = markup.find(quote, i + 1)
                if close < 0:
                    return -1, attrs
                value = markup[i + 1 : close]
                i = close + 1
            elif quote == ">":
                if name in _KEPT_ATTRS and name not in attrs:
                    attrs[name] = ""
                return i + 1, attrs  # a missing value
            else:
                value_start = i
                i = _after(_UNQUOTED, markup, i)
                value = markup[value_start:i]
        if name in _KEPT_ATTRS and name not in attrs:
            attrs[name] = value


def _tag_end(markup: str, start: int) -> int:
    """The index just after the ">" that closes a tag, or -1 when it never closes."""
    return _scan_tag(markup, start)[0]


def _hidden_text(block: str) -> str:
    """The words inside a block that is dropped, without its markup, for scanning."""
    block = block.replace("<!--", " ").replace("-->", " ")
    return html.unescape(re.sub(r"<[^<>]+>", " ", block))


def _drop_blocks(markup: str, hidden_parts: list[str]) -> str:
    """Remove comments, declarations and script, style, noscript, svg and template blocks.

    What is removed goes to `hidden_parts` to be scanned. One pass over the input.
    """
    out: list[str] = []
    pos = 0
    while True:
        found = _OPEN.search(markup, pos)
        if found is None:
            break
        start, opener = found.start(), found.group().lower()
        if opener == "<!--":
            close = markup.find("-->", found.end())
            end = len(markup) if close < 0 else close + 3
        elif opener in ("<!", "<?"):
            close = markup.find(">", found.end())
            end = len(markup) if close < 0 else close + 1
        else:
            opened = _tag_end(markup, found.end())
            closer = (
                _CLOSERS[found.group(1).lower()].search(markup, opened)
                if opened >= 0
                else None
            )
            end = closer.end() if closer else len(markup)
        out.append(markup[pos:start])
        out.append(" ")
        hidden_parts.append(_hidden_text(markup[start:end]))
        pos = end
    out.append(markup[pos:])
    return "".join(out)


def _tags(markup: str) -> Iterator[tuple[int, int, str, str, dict[str, str]]]:
    """Yield (start, end, closing, name, attributes) for each tag, one pass.

    `end` is -1 for a tag that is never closed: the rest of the input belongs to it.
    """
    pos = 0
    while True:
        i = markup.find("<", pos)
        if i < 0:
            return
        named = _NAME.match(markup, i + 1)
        if named is None:
            pos = i + 1  # a "<" that opens nothing is text
            continue
        end, attrs = _scan_tag(markup, named.end())
        if end < 0:
            yield i, -1, "", "", {}
            return
        yield i, end, named.group(1), named.group(2).lower(), attrs
        pos = end


def clean_html(markup: str) -> tuple[str, dict[str, Any]]:
    """Visible text and the hidden content that was removed.

    Returns (text, findings) with findings["hidden_blocks"] (excerpts of hidden
    elements) and findings["hidden_text"] (everything removed, for scanning;
    not reported). The walker keeps a name stack with HTML5 implied end tags, so
    a stray closer cannot end a hidden element early and an unclosed <li> or
    <p> inside one cannot swallow the rest of the page; a `/>` on a non-void
    tag is ignored, as browsers do; unterminated comments and script/style
    blocks hide to the end of input, as browsers do.
    """
    hidden_parts: list[str] = []
    hidden_blocks: list[str] = []
    markup = _drop_blocks(markup, hidden_parts)

    visible: list[str] = []
    hidden_buf: list[str] = []
    positions: dict[str, list[int]] = {}  # open element name -> its stack indexes
    stack: list[str] = []  # open element names, innermost last
    hidden_at = None  # stack index of the element that started the hidden run
    pos = 0

    def emit(text: str) -> None:
        (visible if hidden_at is None else hidden_buf).append(text)

    def flush_hidden() -> None:
        nonlocal hidden_at
        block = _fold(html.unescape("".join(hidden_buf)))
        hidden_buf.clear()
        hidden_at = None
        if block:
            # The excerpt is reported verbatim to the agent, so it carries no
            # invisible characters; the raw block goes to hidden_text, where
            # guard() counts and decodes them. Clean before cutting, or a run of
            # invisible characters at the front would leave an empty excerpt.
            hidden_blocks.append(clean_text(block)[0][:EXCERPT])
            hidden_parts.append(block)

    def pop_to(index: int) -> None:
        for name in reversed(stack[index:]):
            positions[name].pop()
        del stack[index:]
        if hidden_at is not None and hidden_at >= len(stack):
            flush_hidden()

    def last_index(name: str) -> int | None:
        # The last open element of this name, from an index kept per name: scanning the
        # whole stack for every closer is quadratic on many unclosed openers.
        found = positions.get(name)
        return found[-1] if found else None

    for start, end, closing, name, attrs in _tags(markup):
        emit(markup[pos:start])
        if end < 0:  # never closed: the rest of the input is inside this tag
            hidden_parts.append(_hidden_text(markup[start:]))
            pos = len(markup)
            break
        pos = end
        if name in BLOCK:
            emit("\n")
        if closing:
            index = last_index(name)
            if index is not None:
                pop_to(index)
            continue  # a closer with no matching opener is ignored
        if name in VOID:
            continue
        if name in IMPLIED_END and stack and stack[-1] == name:
            pop_to(len(stack) - 1)  # sibling closes the open one
        elif name in CLOSES_P and stack and stack[-1] == "p":
            pop_to(len(stack) - 1)
        stack.append(name)
        positions.setdefault(name, []).append(len(stack) - 1)
        if hidden_at is None and _is_hidden(attrs):
            hidden_at = len(stack) - 1
    emit(markup[pos:])
    if hidden_at is not None:
        flush_hidden()

    text = html.unescape("".join(visible))
    return _fold(text), {
        "hidden_blocks": hidden_blocks,
        "hidden_text": "\n".join(hidden_parts),
    }


def _excerpt(line: str, at: int) -> str:
    """Up to LINE_MAX characters of `line`, always including position `at`.

    The quote is what lets the user dismiss a flag in a second, so it must
    show the match. A fixed `line[:LINE_MAX]` showed the first 200 characters
    of a long paragraph and nothing suspicious when the trigger sat later -
    WebFetch paragraphs and portal plain output routinely run past 200.
    """
    if len(line) <= LINE_MAX:
        return line
    lead = LINE_MAX // 3
    start = max(0, at - lead)
    end = min(len(line), start + LINE_MAX)
    start = max(0, end - LINE_MAX)
    head = "\u2026" if start else ""
    tail = "\u2026" if end < len(line) else ""
    return f"{head}{line[start:end]}{tail}"


def scan(visible: str, hidden: str) -> dict[str, Any]:
    """Instruction-shaped lines, hidden URLs, visible URL count, mixed-script words."""
    seen = set()
    instruction_like = []
    for line in visible.splitlines() + hidden.splitlines():
        stripped = line.strip()
        if not stripped or stripped in seen:
            continue
        match = next(
            (m for m in (p.search(stripped) for p in INSTRUCTION_PATTERNS) if m), None
        )
        if match:
            seen.add(stripped)
            instruction_like.append(_excerpt(stripped, match.start()))
    hidden_urls: list[str] = []
    seen_urls: set[str] = set()
    for url in URL.findall(hidden):
        if url not in seen_urls:
            seen_urls.add(url)
            hidden_urls.append(url)
    homoglyphs: list[str] = []
    seen_words: set[str] = set()
    for word in WORD.findall(visible + "\n" + hidden):
        if word in seen_words:
            continue
        if LATIN.search(word) and CONFUSABLE.search(word):
            seen_words.add(word)
            homoglyphs.append(word)
    return {
        "instruction_like": instruction_like,
        "hidden_urls": hidden_urls,
        "visible_url_count": len(URL.findall(visible)),
        "homoglyph_runs": homoglyphs,
    }


def guard(raw: str, mode: str) -> tuple[str, dict[str, Any]]:
    """Run the whole gate. mode: "html", "text" or "auto". Returns (cleaned, findings)."""
    if mode == "auto":
        mode = "html" if HTML_HINT.search(raw) else "text"
    if mode == "html":
        text, hf = clean_html(raw)
        hidden_text, hidden_blocks = hf["hidden_text"], hf["hidden_blocks"]
    else:
        text, hidden_text, hidden_blocks = raw, "", []
    text, tf = clean_text(text)
    hidden_text, hidden_tf = clean_text(hidden_text)
    # Invisible characters inside hidden content count and alarm like visible
    # ones: a tag-spelled instruction in a display:none block is the same
    # payload, only better hidden. What they spell is hidden content: scanned
    # and reported, never part of the cleaned text.
    for key, n in hidden_tf["invisible_chars"].items():
        tf["invisible_chars"][key] = tf["invisible_chars"].get(key, 0) + n
    tf["invisible_flagged"] += hidden_tf["invisible_flagged"]
    tf["invisible_text"] += hidden_tf["invisible_text"]
    hidden_text = "\n".join([hidden_text, *tf["invisible_text"]])
    findings = {"hidden_blocks": hidden_blocks, **tf, **scan(text, hidden_text)}
    return text, findings


@dataclass(frozen=True)
class Counts:
    """What was found. Counts only: no excerpt of the posting is kept."""

    instruction_like: int
    invisible_in_words: int
    tag_characters: int
    invisible_text: int
    mixed_script_words: int
    hidden_blocks: int
    hidden_urls: int

    @property
    def review(self) -> bool:
        """True for the signals that suggest targeting. Hidden blocks are context only."""
        return (
            self.instruction_like
            + self.invisible_in_words
            + self.tag_characters
            + self.invisible_text
            + self.mixed_script_words
        ) > 0


def clean_posting(raw: str) -> tuple[str, Counts]:
    """The visible text of a pasted posting, and the counts of what was removed or found."""
    text, found = guard(raw, "auto")
    counts = Counts(
        instruction_like=len(found["instruction_like"]),
        invisible_in_words=int(found["invisible_flagged"]),
        tag_characters=int(found["invisible_chars"].get("tag", 0)),
        invisible_text=len(found["invisible_text"]),
        mixed_script_words=len(found["homoglyph_runs"]),
        hidden_blocks=len(found["hidden_blocks"]),
        hidden_urls=len(found["hidden_urls"]),
    )
    return text, counts
