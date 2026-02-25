from collections.abc import AsyncIterator

import asyncpg
import nats
from redis.asyncio import Redis

from auth_service.core.settings import Settings


class Infrastructure:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.db_pool: asyncpg.Pool | None = None
        self.redis: Redis | None = None
        self.nats_client: nats.NATS | None = None

    async def startup(self) -> None:
        self.db_pool = await asyncpg.create_pool(
            dsn=self._settings.database_dsn,
            min_size=self._settings.db_min_pool_size,
            max_size=self._settings.db_max_pool_size,
            command_timeout=15,
        )
        self.redis = Redis.from_url(self._settings.redis_url, encoding="utf-8", decode_responses=True)
        self.nats_client = await nats.connect(
            servers=[self._settings.nats_url],
            connect_timeout=self._settings.nats_connect_timeout,
        )

    async def shutdown(self) -> None:
        if self.nats_client and self.nats_client.is_connected:
            await self.nats_client.close()

        if self.redis:
            await self.redis.aclose()

        if self.db_pool:
            await self.db_pool.close()

    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        if self.db_pool is None:
            raise RuntimeError("Database pool is not initialized")

        async with self.db_pool.acquire() as conn:
            yield conn
