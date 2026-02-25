from contextlib import asynccontextmanager

from fastapi import FastAPI

from auth_service.api.auth import router as auth_router
from auth_service.api.errors import register_exception_handlers
from auth_service.api.health import router as health_router
from auth_service.core.logging import configure_logging
from auth_service.core.settings import get_settings
from auth_service.infrastructure.containers import Infrastructure
from auth_service.infrastructure.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)

    infrastructure = Infrastructure(settings)
    await infrastructure.startup()
    app.state.infrastructure = infrastructure

    configure_telemetry(settings, app)

    try:
        yield
    finally:
        await infrastructure.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(health_router)
    register_exception_handlers(app)
    return app


app = create_app()
