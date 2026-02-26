from redis.asyncio import Redis


class RedisClient:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self.redis: Redis | None = None

    async def startup(self) -> None:
        self.redis = Redis.from_url(self._redis_url, encoding="utf-8", decode_responses=True)

    async def shutdown(self) -> None:
        if self.redis:
            await self.redis.aclose()

    async def ping(self) -> None:
        if self.redis is None:
            raise RuntimeError("Redis is not initialized")
        await self.redis.ping()
