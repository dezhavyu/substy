import asyncio

from notifications_service.services.outbox_publisher import OutboxPublisher


class OutboxWorker:
    def __init__(self, publisher: OutboxPublisher) -> None:
        self._publisher = publisher
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._publisher.run_forever())

    async def stop(self) -> None:
        await self._publisher.stop()
        if self._task:
            await self._task
