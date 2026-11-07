"""App factory. Nothing runs on import: no database, no migrations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from engine.config import Settings, load_settings
from engine.db import Database
from engine.errors import install_error_handlers
from engine.jsonlog import configure_logging
from engine.middleware import RequestContextMiddleware
from engine.routes import health, internal


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Fails fast, naming the variable, if configuration is wrong."""
    settings = settings or load_settings()
    configure_logging(settings.log_level)

    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await database.dispose()

    app = FastAPI(
        lifespan=lifespan,
        title="Jobmigo engine",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.database = database
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(internal.router)
    return app
