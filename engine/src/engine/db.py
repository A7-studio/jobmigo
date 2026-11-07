"""Database access. Nothing connects until a request needs it."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def async_url(url: str) -> str:
    """Use the asyncpg driver whatever form of Postgres URL we were given."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix) :]
    return url


class Database:
    """Lazy holder for the async engine, created on first use."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._engine: AsyncEngine | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(async_url(self._url), pool_pre_ping=True)
        return self._engine

    async def dispose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
