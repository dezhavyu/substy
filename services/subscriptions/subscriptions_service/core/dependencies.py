from collections.abc import AsyncIterator
from uuid import UUID

import asyncpg
from fastapi import Depends, Header, Request

from subscriptions_service.core.exceptions import ForbiddenError, UnauthorizedError
from subscriptions_service.infrastructure.db import Database


def get_db(request: Request) -> Database:
    return request.app.state.db


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


def get_current_roles(x_user_roles: str | None = Header(default="", alias="X-User-Roles")) -> set[str]:
    return {role.strip().lower() for role in x_user_roles.split(",") if role.strip()}


def require_admin(roles: set[str] = Depends(get_current_roles)) -> None:
    if "admin" not in roles:
        raise ForbiddenError()
