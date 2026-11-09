"""The storage interface the CV service uses, and the download-name helper."""

import unicodedata
from typing import Protocol
from urllib.parse import quote


class ObjectStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes | None:
        """The object's bytes, or None when it does not exist."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the object. A missing object is success."""
        ...

    def signed_url(self, key: str, *, expires_seconds: int, download_name: str) -> str:
        """A time-limited GET link that names the file `download_name`."""
        ...


def clean_filename(name: str, *, limit: int = 200) -> str:
    """A display-safe file name: no control characters or path separators."""
    kept = "".join(
        ch for ch in name if unicodedata.category(ch)[0] != "C" and ch not in "/\\"
    )
    return kept.strip()[:limit]


def content_disposition(name: str) -> str:
    """`attachment` header value with an ASCII fallback and an RFC 6266 UTF-8 name."""
    safe = clean_filename(name) or "cv"
    ascii_name = "".join(ch if ch.isascii() and ch not in '"%;' else "_" for ch in safe)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(safe)}"
