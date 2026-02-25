from collections.abc import AsyncIterator

import asyncpg
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

from auth_service.core.jwt import JWTManager
from auth_service.core.rate_limiter import RateLimiter
from auth_service.core.security import PasswordManager, RefreshTokenManager
from auth_service.core.settings import Settings, get_settings
from auth_service.infrastructure.containers import Infrastructure
from auth_service.repositories.sessions import SessionsRepository
from auth_service.repositories.users import UsersRepository
from auth_service.services.auth import AuthService


security_bearer = HTTPBearer(auto_error=False)


def get_infrastructure(request: Request) -> Infrastructure:
    infrastructure: Infrastructure = request.app.state.infrastructure
    return infrastructure


async def get_db_connection(
    infrastructure: Infrastructure = Depends(get_infrastructure),
) -> AsyncIterator[asyncpg.Connection]:
    async for conn in infrastructure.connection():
        yield conn


def get_redis(infrastructure: Infrastructure = Depends(get_infrastructure)) -> Redis:
    if infrastructure.redis is None:
        raise RuntimeError("Redis is not initialized")
    return infrastructure.redis


def get_auth_service(settings: Settings = Depends(get_settings)) -> AuthService:
    return AuthService(
        users_repository=UsersRepository(),
        sessions_repository=SessionsRepository(),
        password_manager=PasswordManager(),
        refresh_token_manager=RefreshTokenManager(settings.refresh_token_pepper),
        jwt_manager=JWTManager(settings),
        refresh_ttl_days=settings.jwt_refresh_token_ttl_days,
    )


def get_rate_limiter(
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> RateLimiter:
    return RateLimiter(redis, settings.rate_limit_window_seconds)


async def get_current_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return credentials.credentials
