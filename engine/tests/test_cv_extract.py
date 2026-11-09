import zipfile

import pytest

from engine.cv.extract import ExtractionError, detect_kind, extract_text, normalise
from engine.cv.limits import (
    MAX_DOCX_ENTRIES,
    MAX_DOCX_XML_BYTES,
    MAX_PDF_PAGES,
    MAX_TEXT_CHARS,
    READ_CHUNK,
)
from tests.cv_fixtures import (
    make_bomb_xml,
    make_docx,
    make_docx_with_hidden_entry,
    make_docx_with_xml,
    make_encrypted_pdf,
    make_pdf,
    make_zip,
    with_understated_size,
)

NBSP = chr(0xA0)


def reason(data: bytes, kind: str) -> str:
    with pytest.raises(ExtractionError) as caught:
        extract_text(data, kind)  # type: ignore[arg-type]
    return caught.value.reason


def test_detect_kind_reads_content_not_names() -> None:
    assert detect_kind(make_pdf(["x"])) == "pdf"
    assert detect_kind(make_docx(["x"])) == "docx"
    assert detect_kind(b"hello") is None
    assert detect_kind(b"") is None
    assert detect_kind(b"\x89PNG\r\n") is None


def test_pdf_text_is_extracted() -> None:
    text = extract_text(make_pdf(["Jane Doe", "Flutter engineer"]), "pdf")
    assert "Jane Doe" in text
    assert "Flutter engineer" in text


def test_docx_text_is_extracted_with_paragraph_breaks() -> None:
    text = extract_text(
        make_docx(["Jane  Doe", "", "", "", "Flutter engineer"]), "docx"
    )
    assert text == "Jane Doe\n\nFlutter engineer"


def test_docx_tabs_breaks_and_escaped_text() -> None:
    xml = (
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
        b'2006/main"><w:body><w:p><w:r><w:t>a &amp; b</w:t><w:tab/><w:t>c</w:t>'
        b"<w:br/><w:t>d</w:t></w:r></w:p></w:body></w:document>"
    )
    assert extract_text(make_docx_with_xml(xml), "docx") == "a & b c\nd"


def test_whitespace_and_control_characters_are_normalised() -> None:
    assert normalise(f"a \t b\x00\r\n\r\n\r\n\r\nc{NBSP} d  ") == "a b\n\nc d"


def test_a_zip_without_a_document_is_unsupported() -> None:
    assert reason(make_zip({"notes.txt": b"hi"}), "docx") == "unsupported"


def test_corrupt_and_empty_files_are_unreadable() -> None:
    assert reason(b"PK\x03\x04 broken", "docx") == "unreadable"
    assert reason(b"%PDF-1.4 broken", "pdf") == "unreadable"
    bad_xml = make_docx_with_xml(b"<w:document")
    assert reason(bad_xml, "docx") == "unreadable"


def test_a_pdf_with_no_text_and_an_empty_docx_have_no_text() -> None:
    assert reason(make_pdf([""]), "pdf") == "no_text"
    assert reason(make_docx([" "]), "docx") == "no_text"


def test_an_encrypted_pdf_is_unreadable() -> None:
    assert reason(make_encrypted_pdf(), "pdf") == "unreadable"


def test_too_many_pages_is_refused() -> None:
    assert reason(make_pdf(["x"] * (MAX_PDF_PAGES + 1)), "pdf") == "too_many_pages"
    assert extract_text(make_pdf(["x"] * MAX_PDF_PAGES), "pdf")


def test_over_long_text_is_refused() -> None:
    long_text = "word " * (MAX_TEXT_CHARS // 4)
    assert reason(make_docx([long_text]), "docx") == "too_long"


def test_a_doctype_is_refused_even_when_harmless() -> None:
    xml = b'<!DOCTYPE d [<!ENTITY e "x">]><w:document xmlns:w="urn:x"/>'
    assert reason(make_docx_with_xml(xml), "docx") == "unreadable"


def test_too_many_entries_is_refused() -> None:
    files = {f"f{i}.txt": b"" for i in range(MAX_DOCX_ENTRIES + 1)}
    files["word/document.xml"] = b"<x/>"
    assert reason(make_zip(files), "docx") == "too_large"


class _Counter:
    """Counts bytes zipfile hands out while inflating."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.total = 0
        original = zipfile.ZipExtFile.read

        def counting(this: zipfile.ZipExtFile, n: int | None = -1) -> bytes:
            data = original(this, n)
            self.total += len(data)
            return data

        monkeypatch.setattr(zipfile.ZipExtFile, "read", counting)


def test_a_bomb_is_refused_after_reading_only_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = _Counter(monkeypatch)
    bomb = make_docx_with_xml(make_bomb_xml(100 * 1024 * 1024))
    assert len(bomb) < 1024 * 1024
    assert reason(bomb, "docx") == "too_large"
    assert counter.total <= MAX_DOCX_XML_BYTES + READ_CHUNK


def test_a_hidden_central_directory_entry_is_still_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = _Counter(monkeypatch)
    hidden = make_docx_with_hidden_entry(100 * 1024 * 1024)
    assert reason(hidden, "docx") == "too_large"
    assert counter.total <= MAX_DOCX_XML_BYTES + READ_CHUNK


def test_an_understated_size_is_bounded_and_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = _Counter(monkeypatch)
    bomb = make_docx_with_xml(make_bomb_xml(100 * 1024 * 1024))
    lying = with_understated_size(bomb, "word/document.xml", 300)
    assert reason(lying, "docx") in {"unreadable", "too_large"}
    assert counter.total <= MAX_DOCX_XML_BYTES + READ_CHUNK


def test_errors_never_contain_file_text() -> None:
    secret = "Jane-Secret-Doe"
    for data, kind in (
        (make_docx_with_xml(f"<w:document>{secret}".encode()), "docx"),
        (make_pdf([secret]) + b"junk", "pdf"),
    ):
        try:
            extract_text(data, kind)  # type: ignore[arg-type]
        except ExtractionError as error:
            assert secret not in str(error)
            assert secret not in repr(error)


def test_an_element_flood_costs_far_less_memory_than_its_xml_size() -> None:
    import tracemalloc

    head = b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p>'
    tail = b"<w:r><w:t>Jane</w:t></w:r></w:p></w:body></w:document>"
    xml = head + b"<w:r/>" * (1_500_000) + tail  # about 9 MB of empty runs
    assert len(xml) < MAX_DOCX_XML_BYTES
    data = make_docx_with_xml(xml)
    tracemalloc.start()
    try:
        assert extract_text(data, "docx") == "Jane"
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert (
        peak < len(xml) * 2
    )  # it was about 20x before finished elements were detached
