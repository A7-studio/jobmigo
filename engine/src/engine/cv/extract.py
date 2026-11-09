"""Text extraction from PDF and DOCX bytes.

This module parses untrusted files. In production it only runs inside the resource-
limited child (`engine.cv.worker`); the functions here also have their own bounds
(page count, inflated bytes counted as produced, text length) so each holds even
without the child. Errors carry a stable reason, never text from the file.
"""

import io
import logging
import re
import zipfile
from typing import IO, Literal
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as DefusedET
from pypdf import PdfReader

from engine.cv.limits import (
    MAX_DOCX_ENTRIES,
    MAX_DOCX_XML_BYTES,
    MAX_PDF_PAGES,
    MAX_TEXT_CHARS,
    READ_CHUNK,
)

# pypdf warnings can quote parts of the file; nothing from it may reach a log.
logging.getLogger("pypdf").setLevel(logging.CRITICAL)

Kind = Literal["pdf", "docx"]
Reason = Literal[
    "unsupported", "unreadable", "no_text", "too_long", "too_many_pages", "too_large"
]
DOCX_MEMBER = "word/document.xml"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ExtractionError(Exception):
    """Extraction failed for a stable reason. The message is the reason only."""

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason)
        self.reason: Reason = reason


def detect_kind(data: bytes) -> Kind | None:
    """Decide the type from the first bytes. DOCX is confirmed later by its content."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"
    return None


_SPACES = re.compile("[ \t\xa0]+")
_BLANK_LINES = re.compile(r"\n{3,}")
# Control characters other than newline and tab; Postgres text also rejects NUL.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def normalise(text: str) -> str:
    text = _CONTROL.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = (_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def _finish(text: str) -> str:
    cleaned = normalise(text)
    if not cleaned:
        raise ExtractionError("no_text")
    if len(cleaned) > MAX_TEXT_CHARS:
        raise ExtractionError("too_long")
    return cleaned


class _LimitedReader(io.RawIOBase):
    """Hands out at most `limit` bytes from `source`, then refuses."""

    def __init__(self, source: IO[bytes], limit: int) -> None:
        self._source = source
        self._left = limit

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray | memoryview) -> int:  # type: ignore[override]
        want = min(len(buffer), READ_CHUNK)
        chunk = self._source.read(want)
        if len(chunk) > self._left:
            raise ExtractionError("too_large")
        self._left -= len(chunk)
        buffer[: len(chunk)] = chunk
        return len(chunk)


def _extract_docx(data: bytes) -> str:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError, OSError):
        raise ExtractionError("unreadable") from None
    with archive:
        if len(archive.infolist()) > MAX_DOCX_ENTRIES:
            raise ExtractionError("too_large")
        if DOCX_MEMBER not in archive.namelist():
            raise ExtractionError("unsupported")
        try:
            with archive.open(DOCX_MEMBER) as member:
                return _docx_text(
                    io.BufferedReader(_LimitedReader(member, MAX_DOCX_XML_BYTES))
                )
        except ExtractionError:
            raise
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError):
            raise ExtractionError("unreadable") from None


def _docx_text(stream: io.BufferedReader) -> str:
    parts: list[str] = []
    size = 0
    open_elements: list[Element] = []
    try:
        events = DefusedET.iterparse(
            stream,
            events=("start", "end"),
            forbid_dtd=True,
        )
        for event, element in events:
            if event == "start":
                open_elements.append(element)
                continue
            open_elements.pop()
            tag: str = element.tag
            piece = ""
            if tag == f"{_W}t":
                piece = element.text or ""
            elif tag == f"{_W}tab":
                piece = "\t"
            elif tag in (f"{_W}br", f"{_W}cr") or tag == f"{_W}p":
                piece = "\n"
            if open_elements:
                # Detach the finished element so memory tracks nesting depth,
                # not the number of elements in the file.
                open_elements[-1].remove(element)
            if piece:
                parts.append(piece)
                size += len(piece)
                if size > MAX_TEXT_CHARS * 2:
                    raise ExtractionError("too_long")
    except ExtractionError:
        raise
    except Exception:  # defused XML errors, malformed XML, bad zip data
        raise ExtractionError("unreadable") from None
    return _finish("".join(parts))


def _extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ExtractionError("unreadable")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ExtractionError("too_many_pages")
        parts: list[str] = []
        size = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            parts.append(text)
            size += len(text)
            if size > MAX_TEXT_CHARS * 2:
                raise ExtractionError("too_long")
    except ExtractionError:
        raise
    except Exception:  # any parser failure on a hostile or broken file
        raise ExtractionError("unreadable") from None
    return _finish("\n".join(parts))


def extract_text(data: bytes, kind: Kind) -> str:
    """The normalised text of a CV, or `ExtractionError` with a stable reason."""
    return _extract_pdf(data) if kind == "pdf" else _extract_docx(data)
