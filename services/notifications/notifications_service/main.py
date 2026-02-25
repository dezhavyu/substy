from contextlib import asynccontextmanager

from fastapi import FastAPI

from notifications_service.api.errors import register_exception_handlers
from notifications_service.api.health import router as health_router
from notifications_service.api.metrics import router as metrics_router
from notifications_service.api.notifications import router as notifications_router
from notifications_service.core.logging import configure_logging
from notifications_service.core.metrics import MetricsRegistry
from notifications_service.core.request_context import RequestContextMiddleware
from notifications_service.core.settings import get_settings
from notifications_service.infrastructure.db import Database
from notifications_service.infrastructure.nats_client import NATSClient
from notifications_service.infrastructure.telemetry import configure_telemetry
from notifications_service.repositories.outbox import OutboxRepository
from notifications_service.services.outbox_publisher import OutboxPublisher
from notifications_service.workers.outbox_worker import OutboxWorker


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)

    db = Database(settings)
    nats_client = NATSClient(settings)
    metrics = MetricsRegistry()

    await db.startup()
    await nats_client.startup()

    app.state.db = db
    app.state.nats = nats_client
    app.state.metrics = metrics

    worker: OutboxWorker | None = None
    if settings.outbox_worker_enabled:
        publisher = OutboxPublisher(
            db=db,
            nats_client=nats_client,
            outbox_repository=OutboxRepository(),
            metrics=metrics,
            settings=settings,
        )
        worker = OutboxWorker(publisher)
        worker.start()

    configure_telemetry(settings, app)

    try:
        yield
    finally:
        if worker:
            await worker.stop()
        await nats_client.shutdown()
        await db.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(notifications_router)

    register_exception_handlers(app)
    return app


app = create_app()
