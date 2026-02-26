from redis.asyncio import Redis


RATE_LIMIT_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


class RedisRateLimiter:
    def __init__(self, redis: Redis, window_seconds: int = 60) -> None:
        self._redis = redis
        self._window_seconds = window_seconds

    async def is_allowed(self, key: str, limit: int) -> bool:
        current = await self._redis.eval(RATE_LIMIT_LUA, 1, key, str(self._window_seconds))
        return int(current) <= limit
