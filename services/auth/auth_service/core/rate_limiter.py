from redis.asyncio import Redis

from auth_service.core.exceptions import RateLimitExceededError


class RateLimiter:
    def __init__(self, redis: Redis, window_seconds: int) -> None:
        self._redis = redis
        self._window_seconds = window_seconds

    async def enforce(self, key: str, limit: int) -> None:
        current = await self._redis.incr(key)
        if current == 1:
            await self._redis.expire(key, self._window_seconds)

        if current > limit:
            raise RateLimitExceededError()
