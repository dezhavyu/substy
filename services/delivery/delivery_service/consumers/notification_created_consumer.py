import json
import logging

from arq.connections import ArqRedis

from delivery_service.core.container import Container
from delivery_service.repositories.delivery_attempts import DeliveryAttemptsRepository
from delivery_service.repositories.processed_events import ProcessedEventsRepository
from delivery_service.schemas.events import NotificationCreatedEvent
from delivery_service.services.fanout import FanoutService
from delivery_service.services.subscriptions_fetcher import SubscriptionsFetcherService

logger = logging.getLogger(__name__)


class NotificationCreatedConsumer:
    def __init__(self, container: Container) -> None:
        self._container = container

    async def run_forever(self) -> None:
        await self._container.nats.ensure_consumer()
        subscription = await self._container.nats.pull_subscribe(
            self._container.settings.nats_subject_notification_created
        )

        redis = ArqRedis.from_url(self._container.settings.redis_url)

        try:
            while True:
                messages = await subscription.fetch(10, timeout=1)
                for msg in messages:
                    try:
                        payload = json.loads(msg.data.decode("utf-8"))
                        event = NotificationCreatedEvent.model_validate(payload)

                        async for conn in self._container.db.connection():
                            service = FanoutService(
                                settings=self._container.settings,
                                processed_events_repository=ProcessedEventsRepository(),
                                attempts_repository=DeliveryAttemptsRepository(),
                                subscriptions_fetcher=SubscriptionsFetcherService(
                                    self._container.subscriptions_client
                                ),
                                metrics=self._container.metrics,
                            )
                            await service.process_notification_created(
                                conn=conn,
                                redis=redis,
                                event=event,
                                subject=msg.subject,
                            )

                        await msg.ack()
                    except Exception:
                        logger.exception("Failed to process notification.created event")
                        await msg.nak(delay=1)
        finally:
            await redis.aclose()
