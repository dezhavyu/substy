from contextlib import asynccontextmanager

from fastapi import FastAPI

from subscriptions_service.api.errors import register_exception_handlers
from subscriptions_service.api.health import router as health_router
from subscriptions_service.api.internal import router as internal_router
from subscriptions_service.api.subscriptions import router as subscriptions_router
from subscriptions_service.api.topics import router as topics_router
from subscriptions_service.core.logging import configure_logging
from subscriptions_service.core.request_context import RequestContextMiddleware
from subscriptions_service.core.settings import get_settings
from subscriptions_service.infrastructure.db import Database
from subscriptions_service.infrastructure.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)

    db = Database(settings)
    await db.startup()
    app.state.db = db

    configure_telemetry(settings, app)

    try:
        yield
    finally:
        await db.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(topics_router)
    app.include_router(subscriptions_router)
    app.include_router(internal_router)

    register_exception_handlers(app)
    return app


app = create_app()
