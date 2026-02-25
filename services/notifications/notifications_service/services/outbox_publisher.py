import logging
from asyncio import Event
from asyncio import TimeoutError as AsyncTimeoutError
from asyncio import wait_for

from notifications_service.core.metrics import MetricsRegistry
from notifications_service.core.settings import Settings
from notifications_service.infrastructure.db import Database
from notifications_service.infrastructure.nats_client import NATSClient
from notifications_service.repositories.outbox import OutboxRepository

logger = logging.getLogger(__name__)


class OutboxPublisher:
    def __init__(
        self,
        db: Database,
        nats_client: NATSClient,
        outbox_repository: OutboxRepository,
        metrics: MetricsRegistry,
        settings: Settings,
    ) -> None:
        self._db = db
        self._nats = nats_client
        self._outbox = outbox_repository
        self._metrics = metrics
        self._settings = settings
        self._stop_event = Event()

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.publish_batch()
            except Exception:
                logger.exception("Outbox publisher loop failure")
            await self._wait_for_interval()

    async def stop(self) -> None:
        self._stop_event.set()

    async def publish_batch(self) -> None:
        async for conn in self._db.connection():
            async with conn.transaction():
                events = await self._outbox.lock_unpublished_batch(conn, self._settings.outbox_batch_size)

                for event in events:
                    timer = self._metrics.start_timer()
                    try:
                        headers = {str(k): str(v) for k, v in event.headers.items()}
                        await self._nats.publish_json(event.event_type, event.payload, headers)
                        await self._outbox.mark_published(conn, event.id)
                        self._metrics.observe_outbox_publish_latency(timer, failed=False)
                    except Exception as exc:
                        await self._outbox.mark_failed(conn, event.id, str(exc))
                        self._metrics.observe_outbox_publish_latency(timer, failed=True)

                unpublished_count = await self._outbox.count_unpublished(conn)
                self._metrics.set_outbox_unpublished_count(unpublished_count)

    async def _wait_for_interval(self) -> None:
        try:
            await wait_for(self._stop_event.wait(), timeout=self._settings.outbox_publish_interval_seconds)
        except AsyncTimeoutError:
            return
