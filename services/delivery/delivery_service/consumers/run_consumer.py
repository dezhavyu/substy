import asyncio

from delivery_service.consumers.notification_created_consumer import NotificationCreatedConsumer
from delivery_service.core.container import build_container, shutdown_container
from delivery_service.core.logging import configure_logging
from delivery_service.core.settings import get_settings


async def main() -> None:
    settings = get_settings()
    configure_logging(settings)

    container = await build_container(settings)
    consumer = NotificationCreatedConsumer(container)

    try:
        await consumer.run_forever()
    finally:
        await shutdown_container(container)


if __name__ == "__main__":
    asyncio.run(main())
