"""Small, generated PDF and DOCX files, including hostile ones. Nothing is stored."""

import io
import struct
import warnings
import zlib
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfWriter

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _pdf_escape(text: str) -> bytes:
    raw = text.encode("latin-1", "replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def make_pdf(pages: list[str], *, content_override: list[bytes] | None = None) -> bytes:
    """A valid PDF with one line of Helvetica text per page.

    `content_override` replaces each page's content stream with a ready-made
    (already encoded) body, declared as Flate, for the hostile fixtures.
    """
    bodies: list[bytes] = []
    page_ids = [4 + 2 * i for i in range(len(pages))]
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    bodies.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    bodies.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    bodies.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for index, text in enumerate(pages):
        content_id = page_ids[index] + 1
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        )
        bodies.append(page.encode())
        if content_override is not None:
            stream = content_override[index]
            head = f"<< /Length {len(stream)} /Filter /FlateDecode >>".encode()
        else:
            stream = b"BT /F1 12 Tf 72 720 Td (" + _pdf_escape(text) + b") Tj ET"
            head = f"<< /Length {len(stream)} >>".encode()
        bodies.append(head + b"\nstream\n" + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(bodies) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(bodies) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


def make_expanding_pdf(expanded_bytes: int) -> bytes:
    """A small PDF whose only content stream inflates to `expanded_bytes`."""
    stream = zlib.compress(b" " * expanded_bytes, 9)
    return make_pdf([""], content_override=[stream])


def make_encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.encrypt("secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _document_xml(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>" for p in paragraphs)
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{_W}">'
        f"<w:body>{body}</w:body></w:document>"
    ).encode()


def make_docx(paragraphs: list[str]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", _document_xml(paragraphs))
    return buffer.getvalue()


def make_docx_with_xml(xml: bytes) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def make_bomb_xml(expanded_bytes: int) -> bytes:
    """Valid XML with `expanded_bytes` of text that compresses to almost nothing."""
    head = f'<w:document xmlns:w="{_W}"><w:body><w:p><w:r><w:t>'.encode()
    tail = b"</w:t></w:r></w:p></w:body></w:document>"
    return head + b"A" * expanded_bytes + tail


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def make_docx_with_hidden_entry(expanded_bytes: int) -> bytes:
    """The end record counts one entry, but the central directory holds a second
    `word/document.xml` (the bomb) that replaces the first when read by name."""
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # duplicate name
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", _document_xml(["honest"]))
            archive.writestr("word/document.xml", make_bomb_xml(expanded_bytes))
    return with_end_record_count(buffer.getvalue(), 1)


def with_end_record_count(data: bytes, count: int) -> bytes:
    end = data.rfind(b"PK\x05\x06")
    patched = bytearray(data)
    patched[end + 8 : end + 12] = struct.pack("<HH", count, count)
    return bytes(patched)


def with_understated_size(data: bytes, name: str, size: int) -> bytes:
    """Rewrite the central directory so `name` claims to be only `size` bytes."""
    patched = bytearray(data)
    position = 0
    while (position := data.find(b"PK\x01\x02", position)) != -1:
        name_length = struct.unpack_from("<H", data, position + 28)[0]
        found = data[position + 46 : position + 46 + name_length].decode()
        if found == name:
            struct.pack_into("<I", patched, position + 24, size)
        position += 4
    return bytes(patched)
