"""Find a quoted stretch of posting text inside one field of the posting.

A quote the model hands back is shown to the user as "the posting says". It has to be
words the posting really has, so it must sit inside a single field (title, company,
location or description) and never span two, must start and end on a word boundary, and
must hold at least one letter or digit. Case and spacing are ignored.
"""

import re
from collections.abc import Sequence


def fold(text: str) -> str:
    """Lowercase, with spaces collapsed, and every line break kept as one "\\n".

    The line breaks matter to readers of the folded text (a denial on one line says
    nothing about the next); `occurrences` ignores them when matching.
    """
    text = re.sub(r"\r\n?|[\u2028\u2029]", "\n", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" ?\n[ \n]*", "\n", text)
    return text.strip().casefold()


def _is_word(char: str) -> bool:
    return char.isalnum() or char == "_"


def occurrences(text: str, quote: str) -> list[int]:
    """Where a folded quote occurs in folded text, on word boundaries.

    Line breaks count as spaces, so a quote the model wrote on one line still matches
    text that wrapped. Positions are those of `text`.
    """
    text, quote = text.replace("\n", " "), quote.replace("\n", " ")
    found: list[int] = []
    at = text.find(quote)
    while at >= 0:
        end = at + len(quote)
        starts_clean = not _is_word(quote[0]) or at == 0 or not _is_word(text[at - 1])
        ends_clean = (
            not _is_word(quote[-1]) or end == len(text) or not _is_word(text[end])
        )
        if starts_clean and ends_clean:
            found.append(at)
        at = text.find(quote, at + 1)
    return found


def usable(quote: str, min_chars: int) -> str | None:
    """The folded quote, or None when it is too short or has no letter or digit."""
    folded = fold(quote)
    if len(folded) < min_chars or not any(c.isalnum() for c in folded):
        return None
    return folded


def locate(
    fields: Sequence[str | None], quote: str, *, min_chars: int
) -> tuple[int, int] | None:
    """(field index, start in that folded field) of the first place the quote sits."""
    folded = usable(quote, min_chars)
    if folded is None:
        return None
    for index, field in enumerate(fields):
        if not field:
            continue
        spots = occurrences(fold(field), folded)
        if spots:
            return index, spots[0]
    return None
