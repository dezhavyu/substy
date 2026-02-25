import os

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5433")
os.environ.setdefault("DB_NAME", "auth")
os.environ.setdefault("DB_USER", "auth")
os.environ.setdefault("DB_PASSWORD", "auth")
os.environ.setdefault("REDIS_URL", "redis://localhost:63790/0")
os.environ.setdefault("NATS_URL", "nats://localhost:4223")
os.environ.setdefault("OTEL_ENABLED", "false")

from auth_service.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
