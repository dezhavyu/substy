import os
from pathlib import Path

import asyncpg
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5434")
os.environ.setdefault("DB_NAME", "subscriptions")
os.environ.setdefault("DB_USER", "subscriptions")
os.environ.setdefault("DB_PASSWORD", "subscriptions")
os.environ.setdefault("OTEL_ENABLED", "false")

from subscriptions_service.core.settings import get_settings
from subscriptions_service.main import create_app


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_dsn)
    try:
        migration_path = Path(__file__).resolve().parents[2] / "migrations" / "001_init.sql"
        sql = migration_path.read_text(encoding="utf-8")
        await conn.execute(sql)
        await conn.execute("TRUNCATE subscriptions.subscriptions, subscriptions.topics CASCADE")
    finally:
        await conn.close()


@pytest.fixture
async def client():
    app = create_app()
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
