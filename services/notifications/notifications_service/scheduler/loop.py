import logging
from asyncio import Event
from asyncio import TimeoutError as AsyncTimeoutError
from asyncio import wait_for
from time import perf_counter

from notifications_service.infrastructure.db import Database
from notifications_service.services.scheduler_service import SchedulerService

logger = logging.getLogger(__name__)


class SchedulerLoop:
    def __init__(self, service: SchedulerService, tick_interval_seconds: float) -> None:
        self._service = service
        self._tick_interval_seconds = tick_interval_seconds
        self._stop_event = Event()

    async def run_forever(self, db: Database) -> None:
        while not self._stop_event.is_set():
            try:
                started_at = perf_counter()
                async for conn in db.connection():
                    result = await self._service.run_one_tick(conn)
                latency_ms = round((perf_counter() - started_at) * 1000.0, 2)
                logger.info(
                    "scheduler_tick",
                    extra={
                        "picked_count": result.picked_count,
                        "batch_latency_ms": latency_ms,
                        "scheduled_due_count": result.due_count,
                        "scheduled_backlog_count": result.backlog_count,
                    },
                )
            except Exception:
                logger.exception("Scheduler loop failure")

            await self._wait_for_interval()

    async def stop(self) -> None:
        self._stop_event.set()

    async def _wait_for_interval(self) -> None:
        try:
            await wait_for(self._stop_event.wait(), timeout=self._tick_interval_seconds)
        except AsyncTimeoutError:
            return
