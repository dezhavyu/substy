import os
from pathlib import Path

import asyncpg
import pytest
from arq.connections import ArqRedis, RedisSettings, create_pool

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5436")
os.environ.setdefault("DB_NAME", "delivery")
os.environ.setdefault("DB_USER", "delivery")
os.environ.setdefault("DB_PASSWORD", "delivery")
os.environ.setdefault("REDIS_URL", "redis://localhost:63791/0")
os.environ.setdefault("NATS_URL", "nats://localhost:4225")
os.environ.setdefault("OTEL_ENABLED", "false")

from delivery_service.core.settings import get_settings


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_dsn)
    try:
        migration_path = Path(__file__).resolve().parents[2] / "migrations" / "001_init.sql"
        await conn.execute(migration_path.read_text(encoding="utf-8"))
    finally:
        await conn.close()


@pytest.fixture
async def clean_database():
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_dsn)
    try:
        await conn.execute("TRUNCATE delivery.delivery_attempts, delivery.processed_events")
        yield
    finally:
        await conn.close()


@pytest.fixture
async def redis_pool():
    settings = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.flushdb()
    try:
        yield redis
    finally:
        await redis.flushdb()
        await redis.aclose()
