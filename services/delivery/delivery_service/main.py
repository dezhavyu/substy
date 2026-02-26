from contextlib import asynccontextmanager

from fastapi import FastAPI

from delivery_service.api.errors import register_exception_handlers
from delivery_service.api.health import router as health_router
from delivery_service.api.metrics import router as metrics_router
from delivery_service.core.container import build_container, shutdown_container
from delivery_service.core.logging import configure_logging
from delivery_service.core.request_context import RequestContextMiddleware
from delivery_service.core.settings import get_settings
from delivery_service.infrastructure.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)

    container = await build_container(settings)
    app.state.container = container

    configure_telemetry(settings, app)

    try:
        yield
    finally:
        await shutdown_container(container)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(metrics_router)

    register_exception_handlers(app)
    return app


app = create_app()
