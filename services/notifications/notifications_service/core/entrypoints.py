import asyncio
import signal
from asyncio import Event

from notifications_service.core.logging import configure_logging
from notifications_service.core.metrics import MetricsRegistry
from notifications_service.core.settings import get_settings
from notifications_service.infrastructure.db import Database
from notifications_service.infrastructure.nats_client import NATSClient
from notifications_service.infrastructure.telemetry import configure_telemetry
from notifications_service.repositories.notifications import NotificationsRepository
from notifications_service.repositories.outbox import OutboxRepository
from notifications_service.scheduler.loop import SchedulerLoop
from notifications_service.services.outbox_publisher import OutboxPublisher
from notifications_service.services.scheduler_service import SchedulerService


def _install_signal_handlers(stop_event: Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            continue


async def run_outbox_publisher_process() -> None:
    settings = get_settings()
    configure_logging(settings)
    configure_telemetry(settings, app=None)

    db = Database(settings)
    nats_client = NATSClient(settings)
    metrics = MetricsRegistry()

    await db.startup()
    await nats_client.startup()

    publisher = OutboxPublisher(
        db=db,
        nats_client=nats_client,
        outbox_repository=OutboxRepository(),
        metrics=metrics,
        settings=settings,
    )

    stop_event = Event()
    _install_signal_handlers(stop_event)
    task = asyncio.create_task(publisher.run_forever())

    try:
        await stop_event.wait()
    finally:
        await publisher.stop()
        await task
        await nats_client.shutdown()
        await db.shutdown()


async def run_scheduler_process() -> None:
    settings = get_settings()
    configure_logging(settings)
    configure_telemetry(settings, app=None)

    db = Database(settings)
    metrics = MetricsRegistry()
    service = SchedulerService(
        notifications_repository=NotificationsRepository(),
        outbox_repository=OutboxRepository(),
        settings=settings,
        metrics=metrics,
    )
    scheduler = SchedulerLoop(service=service, tick_interval_seconds=settings.scheduler_tick_interval_seconds)

    await db.startup()

    stop_event = Event()
    _install_signal_handlers(stop_event)
    task = asyncio.create_task(scheduler.run_forever(db))

    try:
        await stop_event.wait()
    finally:
        await scheduler.stop()
        await task
        await db.shutdown()
