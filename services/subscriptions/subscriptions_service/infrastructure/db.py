from collections.abc import AsyncIterator

import asyncpg

from subscriptions_service.core.settings import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None

    async def startup(self) -> None:
        self._pool = await asyncpg.create_pool(
            dsn=self._settings.database_dsn,
            min_size=self._settings.db_min_pool_size,
            max_size=self._settings.db_max_pool_size,
            command_timeout=15,
        )

    async def shutdown(self) -> None:
        if self._pool:
            await self._pool.close()

    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        if self._pool is None:
            raise RuntimeError("DB pool is not initialized")

        async with self._pool.acquire() as connection:
            yield connection

    async def ping(self) -> None:
        if self._pool is None:
            raise RuntimeError("DB pool is not initialized")

        async with self._pool.acquire() as connection:
            await connection.fetchval("SELECT 1")
