import asyncio

from notifications_service.core.entrypoints import run_outbox_publisher_process


if __name__ == "__main__":
    asyncio.run(run_outbox_publisher_process())
