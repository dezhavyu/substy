from collections.abc import AsyncIterator
from uuid import UUID

import asyncpg
from fastapi import Depends, Header, Request

from notifications_service.core.exceptions import UnauthorizedError
from notifications_service.core.metrics import MetricsRegistry
from notifications_service.infrastructure.db import Database
from notifications_service.infrastructure.nats_client import NATSClient


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_nats(request: Request) -> NATSClient:
    return request.app.state.nats


def get_metrics(request: Request) -> MetricsRegistry:
    return request.app.state.metrics


async def get_connection(db: Database = Depends(get_db)) -> AsyncIterator[asyncpg.Connection]:
    async for conn in db.connection():
        yield conn


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def get_current_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> UUID:
    if not x_user_id:
        raise UnauthorizedError()
    try:
        return UUID(x_user_id)
    except ValueError as exc:
        raise UnauthorizedError() from exc


def get_roles(x_user_roles: str | None = Header(default="", alias="X-User-Roles")) -> set[str]:
    return {role.strip().lower() for role in x_user_roles.split(",") if role.strip()}
