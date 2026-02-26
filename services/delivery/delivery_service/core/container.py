from dataclasses import dataclass

from delivery_service.core.metrics import MetricsRegistry
from delivery_service.core.settings import Settings
from delivery_service.infrastructure.db import Database
from delivery_service.infrastructure.http_client import SubscriptionsClient
from delivery_service.infrastructure.nats_client import NATSClient
from delivery_service.infrastructure.redis_client import RedisClient


@dataclass
class Container:
    settings: Settings
    metrics: MetricsRegistry
    db: Database
    redis: RedisClient
    nats: NATSClient
    subscriptions_client: SubscriptionsClient


async def build_container(settings: Settings) -> Container:
    metrics = MetricsRegistry()
    db = Database(settings)
    redis = RedisClient(settings.redis_url)
    nats = NATSClient(settings)
    subscriptions_client = SubscriptionsClient(settings, metrics)

    await db.startup()
    await redis.startup()
    await nats.startup()
    await subscriptions_client.startup()

    return Container(
        settings=settings,
        metrics=metrics,
        db=db,
        redis=redis,
        nats=nats,
        subscriptions_client=subscriptions_client,
    )


async def shutdown_container(container: Container) -> None:
    await container.subscriptions_client.shutdown()
    await container.nats.shutdown()
    await container.redis.shutdown()
    await container.db.shutdown()
