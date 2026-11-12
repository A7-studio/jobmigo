"""The PDF and DOCX files: built in memory, then read back the way a parser would."""

import io
from typing import Any

from docx import Document
from pypdf import PdfReader

from engine.jobs.kit_export import Doc, Line, build_doc, render_docx, render_pdf
from tests.test_kit_edit import answers_content, cv_content, letter_content


def lines_of(doc: Doc) -> list[tuple[str, str]]:
    return [(line.kind, line.text) for line in doc.lines]


def pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_a_cv_has_a_header_then_the_standard_sections_in_order() -> None:
    content, _ = cv_content()
    doc = build_doc(content, "Sam Gichu", "sam@example.com | Nairobi", "CV")
    kinds = lines_of(doc)
    assert kinds[:2] == [
        ("title", "Sam Gichu"),
        ("contact", "sam@example.com | Nairobi"),
    ]
    headings = [text for kind, text in kinds if kind == "heading"]
    assert headings == ["Summary", "Experience", "Skills"]
    assert ("subheading", "Lead at BeatBnk (2025-2026)") in [
        (k, t) for k, t in kinds if t.startswith("Lead")
    ] or any(k == "subheading" and t.startswith("Lead at BeatBnk") for k, t in kinds)
    bullets = [text for kind, text in kinds if kind == "bullet"]
    assert bullets[:2] == ["Cut bugs by 60%.", "Won 3 awards."]
    assert kinds[-1] == ("paragraph", "Flutter")
    assert doc.title == "Sam Gichu - CV" and doc.author == "Sam Gichu"


def test_projects_education_and_empty_bullets() -> None:
    content: dict[str, Any] = {
        "docType": "cv",
        "summary": {"text": ""},
        "entries": [
            {"kind": "education", "heading": "BSc at Meru", "bullets": []},
            {
                "kind": "project",
                "heading": "Kakitoo",
                "bullets": [{"text": " "}, {"text": "M-PESA."}],
            },
            {"kind": "experience", "heading": "Role at A", "bullets": []},
        ],
        "skills": [],
    }
    kinds = lines_of(build_doc(content, "S", "", "CV"))
    assert [t for k, t in kinds if k == "heading"] == [
        "Experience",
        "Projects",
        "Education",
    ]
    assert [t for k, t in kinds if k == "bullet"] == ["M-PESA."]
    assert not any(k == "contact" for k, _ in kinds)  # no contact line given


def test_a_letter_has_a_greeting_a_closing_and_the_name() -> None:
    doc = build_doc(letter_content(), "Sam Gichu", "", "Cover letter")
    texts = [t for _, t in lines_of(doc)]
    assert texts == [
        "Sam Gichu",
        "Dear hiring team,",
        "I lead Flutter.",
        "I cut bugs by 60%.",
        "Kind regards,",
        "Sam Gichu",
    ]


def test_a_proposal_has_no_greeting_and_answers_pair_each_question() -> None:
    proposal = dict(letter_content(), docType="proposal")
    texts = [t for _, t in lines_of(build_doc(proposal, "Sam", "", "Proposal"))]
    assert "Dear hiring team," not in texts and "Kind regards," not in texts
    assert texts[-1] == "Sam"
    kinds = lines_of(build_doc(answers_content(), "Sam", "", "Answers"))
    assert kinds[-2:] == [("bold", "Flutter?"), ("paragraph", "Yes, Flutter.")]


def test_the_pdf_is_selectable_text_in_reading_order() -> None:
    content, _ = cv_content()
    data = render_pdf(build_doc(content, "Sam Gichu", "sam@example.com", "CV"))
    assert data.startswith(b"%PDF")
    text = pdf_text(data)
    assert "(cid:" not in text and "�" not in text
    order = [
        "Sam Gichu",
        "sam@example.com",
        "Summary",
        "Flutter lead.",
        "Experience",
        "Cut bugs by 60%.",
        "Skills",
        "Flutter",
    ]
    positions = [text.index(item) for item in order[:-1]]
    positions.append(text.rindex(order[-1]))  # the skill, not the word in the summary
    assert positions == sorted(positions)
    assert "•" in text  # bullets are real characters
    reader = PdfReader(io.BytesIO(data))
    assert reader.metadata is not None
    assert reader.metadata.author == "Sam Gichu"
    assert reader.metadata.title == "Sam Gichu - CV"


def test_markup_and_accents_come_through_as_the_person_wrote_them() -> None:
    doc = Doc(
        "t",
        "a",
        [
            Line("title", "José Müller"),
            Line("paragraph", '<b>bold</b> & <i>x</i> &amp; "quoted" 5 < 6'),
        ],
    )
    text = pdf_text(render_pdf(doc))
    assert "José Müller" in text
    assert '<b>bold</b> & <i>x</i> &amp; "quoted" 5 < 6' in text


def test_a_character_the_font_cannot_draw_becomes_a_question_mark() -> None:
    text = pdf_text(render_pdf(Doc("t", "a", [Line("paragraph", "Hello 世界 ok")])))
    assert "Hello ?? ok" in text


def test_a_long_document_runs_onto_more_pages_and_a_long_word_does_not_break_it() -> (
    None
):
    lines = [Line("heading", "Experience")]
    for n in range(80):
        lines.append(Line("subheading", f"Role {n} at Company"))
        lines += [
            Line("bullet", f"Did thing {n}.{m} " + "word " * 25) for m in range(3)
        ]
    lines.append(Line("paragraph", "x" * 400))
    data = render_pdf(Doc("t", "a", lines))
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) > 2
    assert "Role 79 at Company" in pdf_text(data)


def test_the_docx_has_real_styles_and_the_same_text() -> None:
    content, _ = cv_content()
    data = render_docx(build_doc(content, "Sam Gichu", "sam@example.com", "CV"))
    assert data[:2] == b"PK"
    document = Document(io.BytesIO(data))
    rows = [(p.style.name if p.style else "", p.text) for p in document.paragraphs]
    assert rows[0] == ("Title", "Sam Gichu")
    assert rows[1] == ("Normal", "sam@example.com")
    assert ("Heading 1", "Summary") in rows and ("Heading 1", "Experience") in rows
    assert any(s == "Heading 2" and t.startswith("Lead at BeatBnk") for s, t in rows)
    assert ("List Bullet", "Cut bugs by 60%.") in rows
    assert rows[-1] == ("Normal", "Flutter")
    assert document.core_properties.author == "Sam Gichu"
    assert document.core_properties.title == "Sam Gichu - CV"
    assert not document.tables and not document.inline_shapes


def test_control_characters_cannot_break_either_file() -> None:
    doc = Doc(
        "t",
        "a",
        [Line("title", "Sam\x00\x0b"), Line("bullet", "ok\x01\x1f\ud800 fine ￾")],
    )
    assert "Sam" in pdf_text(render_pdf(doc))
    document = Document(io.BytesIO(render_docx(doc)))
    assert [p.text for p in document.paragraphs] == ["Sam", "ok fine "]


def test_an_empty_document_still_renders() -> None:
    for content in ({}, {"docType": "cv"}, {"docType": "answers"}):
        doc = build_doc(content, "Sam", "", "x")
        assert render_pdf(doc).startswith(b"%PDF")
        assert render_docx(doc)[:2] == b"PK"


def test_the_pdf_counts_the_characters_it_cannot_draw_and_the_docx_keeps_them() -> None:
    from engine.jobs.kit_export import count_undrawable

    cyrillic = Doc("t", "a", [Line("title", "Анна"), Line("paragraph", "ok")])
    assert count_undrawable(cyrillic) == 4
    plain = Doc("t", "a", [Line("title", "José Müller"), Line("paragraph", "ok")])
    assert count_undrawable(plain) == 0
    mixed = Doc("t", "a", [Line("paragraph", "a✓b✓ 世")])
    assert count_undrawable(mixed) == 3
    document = Document(io.BytesIO(render_docx(cyrillic)))
    assert document.paragraphs[0].text == "Анна"


def test_the_docx_has_plain_black_fonts_no_theme_fonts_no_border_and_todays_date() -> (
    None
):
    import datetime
    import zipfile

    data = render_docx(
        Doc(
            "t",
            "a",
            [Line("title", "Sam"), Line("heading", "Summary"), Line("subheading", "x")],
        )
    )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        styles = archive.read("word/styles.xml").decode()
    document = Document(io.BytesIO(data))
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "List Bullet"):
        rpr = document.styles[name].element.rPr
        assert rpr is not None
        fonts = rpr.rFonts
        assert fonts is not None, name
        assert (
            fonts.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii"
            )
            == "Arial"
        ), name
        for attribute in fonts.attrib:
            assert "Theme" not in attribute, (name, attribute)
    title = document.styles["Title"].element
    assert (
        title.pPr is None
        or title.pPr.find(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pBdr"
        )
        is None
    )
    assert "4F81BD" not in styles.split('w:styleId="Title"')[1].split("</w:style>")[0]
    created = document.core_properties.created
    assert created.year >= datetime.datetime.now(datetime.UTC).year
