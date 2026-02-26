import pytest

from bff_gateway.rate_limit.limiter import RedisRateLimiter


class FakeRedis:
    def __init__(self):
        self.counter = 0

    async def eval(self, script, keys, key, window):
        self.counter += 1
        return self.counter


@pytest.mark.asyncio
async def test_rate_limiter_returns_429_condition():
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis)

    assert await limiter.is_allowed("k", 1) is True
    assert await limiter.is_allowed("k", 1) is False
