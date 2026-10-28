"""FastAPI application factory and ASGI entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .core.config import Settings, get_settings
from .core.exceptions import register_exception_handlers
from .core.middleware import setup_middleware
from .db import init_db
from .routers import examples

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare resources on startup."""
    await init_db()
    logger.info("Started %s", app.title)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application from settings."""
    config = settings or get_settings()
    logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)

    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        docs_url=config.DOCS_URL,
        openapi_url=config.OPENAPI_URL,
        lifespan=lifespan,
    )
    setup_middleware(app, config)
    register_exception_handlers(app)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Report liveness and the running version."""
        return {"status": "ok", "version": config.APP_VERSION, "environment": config.ENVIRONMENT}

    app.include_router(examples.router, prefix=config.API_V1_PREFIX)
    return app


app = create_app()
