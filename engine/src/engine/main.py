"""App factory. Nothing runs on import: no database, no migrations."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from engine.config import Settings, load_settings
from engine.cv.parse_service import ParseJobs, sweep_interrupted
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
    parse_jobs = ParseJobs(database)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            # A restart loses in-process parses; make their rows retryable.
            await sweep_interrupted(database)
        except Exception:
            logging.getLogger("engine").warning("parse sweep failed at startup")
        yield
        await parse_jobs.shutdown()
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
    app.state.parse_jobs = parse_jobs
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(internal.router)
    return app
