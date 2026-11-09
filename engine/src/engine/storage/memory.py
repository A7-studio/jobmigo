"""An in-memory store for tests. Signed links are placeholders, not real URLs."""

from urllib.parse import quote

from engine.storage.store import clean_filename


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def get(self, key: str) -> bytes | None:
        found = self.objects.get(key)
        return found[0] if found else None

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def signed_url(self, key: str, *, expires_seconds: int, download_name: str) -> str:
        name = quote(clean_filename(download_name) or "cv")
        return f"memory://{quote(key)}?expires={expires_seconds}&name={name}"
