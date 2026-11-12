"""Turn a checked kit document into a plain PDF or DOCX, in memory.

The layout is one column of text for the sake of applicant tracking systems: no
tables, images or text boxes, real headings and bullets, text that extracts in reading
order. The only words code adds are the ones in `_LETTER_GREETING`,
`_LETTER_CLOSING` and the section headings; everything else comes from the version and
the name and contact line the person wrote. Text is cleaned of characters that break the
file formats, and the PDF replaces a character its font cannot draw with `?` instead of
a blank box. Nothing here logs text.
"""

import datetime
import io
import os
import re
from dataclasses import dataclass
from typing import Any, Literal
from xml.sax.saxutils import escape

import reportlab
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

Kind = Literal[
    "title", "contact", "heading", "subheading", "paragraph", "bullet", "bold"
]

DOC_LABELS = {
    "cv": "CV",
    "letter": "Cover letter",
    "proposal": "Proposal",
    "answers": "Answers",
}
_LETTER_GREETING = "Dear hiring team,"
_LETTER_CLOSING = "Kind regards,"
_SECTIONS = {
    "experience": "Experience",
    "project": "Projects",
    "education": "Education",
}
# Characters that cannot appear in an XML document, so not in a DOCX.
_BAD_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")


@dataclass(frozen=True)
class Line:
    kind: Kind
    text: str


@dataclass(frozen=True)
class Doc:
    """What a file holds, in reading order."""

    title: str
    author: str
    lines: list[Line]


def _text(value: object) -> str:
    return _BAD_XML.sub("", str(value or "")).strip()


def _header(name: str, contact: str) -> list[Line]:
    lines = [Line("title", name)]
    if contact:
        lines.append(Line("contact", contact))
    return lines


def build_doc(content: dict[str, Any], name: str, contact: str, label: str) -> Doc:
    """The lines of a version's file. `label` names the document in its title."""
    name, contact = _text(name), _text(contact)
    lines = _header(name, contact)
    kind = content.get("docType")
    if kind == "cv":
        summary = _text(content.get("summary", {}).get("text"))
        if summary:
            lines += [Line("heading", "Summary"), Line("paragraph", summary)]
        for kind_name, heading in _SECTIONS.items():
            entries = [
                e for e in content.get("entries", []) if e.get("kind") == kind_name
            ]
            if not entries:
                continue
            lines.append(Line("heading", heading))
            for entry in entries:
                lines.append(Line("subheading", _text(entry.get("heading"))))
                for bullet in entry.get("bullets", []):
                    if _text(bullet.get("text")):
                        lines.append(Line("bullet", _text(bullet.get("text"))))
        skills = [_text(s.get("name")) for s in content.get("skills", [])]
        skills = [s for s in skills if s]
        if skills:
            lines += [Line("heading", "Skills"), Line("paragraph", ", ".join(skills))]
    elif kind in ("letter", "proposal"):
        if kind == "letter":
            lines.append(Line("paragraph", _LETTER_GREETING))
        lines += [
            Line("paragraph", _text(p.get("text")))
            for p in content.get("paragraphs", [])
            if _text(p.get("text"))
        ]
        if kind == "letter":
            lines.append(Line("paragraph", _LETTER_CLOSING))
        lines.append(Line("paragraph", name))
    elif kind == "answers":
        lines.append(Line("heading", "Answers"))
        for answer in content.get("answers", []):
            lines.append(Line("bold", _text(answer.get("question"))))
            lines.append(Line("paragraph", _text(answer.get("text"))))
    return Doc(title=f"{name} - {label}", author=name, lines=lines)


# --- PDF -------------------------------------------------------------------------

_FONTS = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
_REGULAR, _BOLD = "JobmigoVera", "JobmigoVeraBold"
_registered = False


def _register_fonts() -> None:
    global _registered
    if _registered:
        return
    pdfmetrics.registerFont(TTFont(_REGULAR, os.path.join(_FONTS, "Vera.ttf")))
    pdfmetrics.registerFont(TTFont(_BOLD, os.path.join(_FONTS, "VeraBd.ttf")))
    pdfmetrics.registerFontFamily(_REGULAR, normal=_REGULAR, bold=_BOLD)
    _registered = True


def _drawable(text: str) -> str:
    """Replace a character the font has no glyph for with `?`."""
    font = pdfmetrics.getFont(_REGULAR)
    glyphs = font.face.charToGlyph
    return "".join(
        ch if ch in ("\n", "\t") or ord(ch) in glyphs else "?" for ch in text
    )


def count_undrawable(doc: Doc) -> int:
    """How many characters of the document the PDF font cannot draw (shown as `?`)."""
    _register_fonts()
    glyphs = pdfmetrics.getFont(_REGULAR).face.charToGlyph
    return sum(
        1
        for line in doc.lines
        for ch in line.text
        if ch not in "\n\t" and ord(ch) not in glyphs
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle(
        "base", fontName=_REGULAR, fontSize=10, leading=13.5, alignment=TA_LEFT
    )
    return {
        "title": ParagraphStyle(
            "title", parent=base, fontName=_BOLD, fontSize=17, leading=21
        ),
        "contact": ParagraphStyle("contact", parent=base, spaceAfter=6),
        "heading": ParagraphStyle(
            "heading",
            parent=base,
            fontName=_BOLD,
            fontSize=11.5,
            leading=14,
            spaceBefore=9,
            spaceAfter=3,
            keepWithNext=1,
        ),
        "subheading": ParagraphStyle(
            "subheading", parent=base, fontName=_BOLD, spaceBefore=5, keepWithNext=1
        ),
        "paragraph": ParagraphStyle("paragraph", parent=base, spaceAfter=6),
        "bold": ParagraphStyle(
            "bold", parent=base, fontName=_BOLD, spaceBefore=4, keepWithNext=1
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base, leftIndent=12, firstLineIndent=-9, spaceAfter=1.5
        ),
    }


def render_pdf(doc: Doc) -> bytes:
    """A4, one column, selectable text, the Vera font."""
    _register_fonts()
    styles = _styles()
    story: list[Any] = []
    for line in doc.lines:
        text = escape(_drawable(line.text)).replace("\n", "<br/>")
        if not text:
            story.append(Spacer(1, 4))
        elif line.kind == "bullet":
            # The bullet is part of the text, so it extracts as a real character.
            story.append(Paragraph(f"\u2022 {text}", styles["bullet"]))
        else:
            story.append(Paragraph(text, styles[line.kind]))
    buffer = io.BytesIO()
    SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=_text(doc.title),
        author=_text(doc.author),
        creator="Jobmigo",
    ).build(story)
    return buffer.getvalue()


# --- DOCX ------------------------------------------------------------------------


def _plain_font(element: Any) -> None:
    """Arial everywhere, with no theme font that Word would prefer, and no border."""
    fonts = element.rPr.rFonts
    for attribute in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(qn(f"w:{attribute}"), None)
    for attribute in ("eastAsia", "cs"):
        fonts.set(qn(f"w:{attribute}"), "Arial")
    border = element.pPr.find(qn("w:pBdr")) if element.pPr is not None else None
    if border is not None:
        element.pPr.remove(border)


def render_docx(doc: Doc) -> bytes:
    """Real Title, Heading and List Bullet styles in a plain black font."""
    document = Document()
    document.core_properties.title = _text(doc.title)
    document.core_properties.author = _text(doc.author)
    document.core_properties.comments = ""
    for style_name, size, bold in (
        ("Normal", 10.5, False),
        ("Title", 17, True),
        ("Heading 1", 12, True),
        ("Heading 2", 10.5, True),
        ("List Bullet", 10.5, False),
    ):
        style = document.styles[style_name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.color.rgb = RGBColor(0, 0, 0)
        _plain_font(style.element)
    now = datetime.datetime.now(datetime.UTC)
    document.core_properties.created = now
    document.core_properties.modified = now
    document.core_properties.last_modified_by = ""
    section = document.sections[0]
    section.left_margin = section.right_margin = Pt(57)
    section.top_margin = section.bottom_margin = Pt(51)
    for line in doc.lines:
        text = _BAD_XML.sub("", line.text)
        if line.kind == "title":
            document.add_paragraph(text, style="Title")
        elif line.kind == "heading":
            document.add_heading(text, level=1)
        elif line.kind == "subheading":
            document.add_heading(text, level=2)
        elif line.kind == "bullet":
            document.add_paragraph(text, style="List Bullet")
        elif line.kind == "bold":
            document.add_paragraph().add_run(text).bold = True
        else:
            document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
