from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from bff_gateway.api.auth import router as auth_router
from bff_gateway.api.notifications import router as notifications_router
from bff_gateway.api.subscriptions import router as subscriptions_router
from bff_gateway.api.system import router as system_router
from bff_gateway.clients.downstream import build_service_clients
from bff_gateway.core.body_limit import BodySizeLimitMiddleware
from bff_gateway.core.exceptions_handler import register_exception_handlers
from bff_gateway.core.logging import configure_logging
from bff_gateway.core.request_context import RequestContextMiddleware
from bff_gateway.core.settings import get_settings
from bff_gateway.observability.access_log import AccessLogMiddleware
from bff_gateway.observability.metrics import MetricsRegistry
from bff_gateway.observability.telemetry import configure_telemetry
from bff_gateway.security.jwt import JWTVerifier

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)

    clients = build_service_clients(settings)
    redis = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    metrics = MetricsRegistry()
    jwt_verifier = JWTVerifier(settings)

    app.state.clients = clients
    app.state.redis = redis
    app.state.metrics = metrics
    app.state.jwt_verifier = jwt_verifier

    configure_telemetry(settings, app)

    try:
        yield
    finally:
        await clients.aclose()
        await redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id", "Idempotency-Key"],
    )
    app.add_middleware(AccessLogMiddleware, logger=logger)

    app.include_router(system_router)
    app.include_router(auth_router)
    app.include_router(subscriptions_router)
    app.include_router(subscriptions_router, prefix="/api")
    app.include_router(notifications_router)
    app.include_router(notifications_router, prefix="/api")

    register_exception_handlers(app)
    return app


app = create_app()
