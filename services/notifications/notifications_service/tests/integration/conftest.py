import os
from pathlib import Path

import asyncpg
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5435")
os.environ.setdefault("DB_NAME", "notifications")
os.environ.setdefault("DB_USER", "notifications")
os.environ.setdefault("DB_PASSWORD", "notifications")
os.environ.setdefault("NATS_URL", "nats://localhost:4224")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("OUTBOX_WORKER_ENABLED", "false")

from notifications_service.core.settings import get_settings
from notifications_service.main import create_app


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_dsn)
    try:
        migration_path = Path(__file__).resolve().parents[2] / "migrations" / "001_init.sql"
        await conn.execute("DROP SCHEMA IF EXISTS notifications CASCADE")
        await conn.execute(migration_path.read_text(encoding="utf-8"))
    finally:
        await conn.close()


@pytest.fixture
async def clean_database():
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_dsn)
    try:
        await conn.execute("TRUNCATE notifications.outbox_events, notifications.notifications")
        yield
    finally:
        await conn.close()


@pytest.fixture
async def client(clean_database):
    app = create_app()
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
