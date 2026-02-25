import asyncpg
from fastapi import APIRouter, Depends, Request, Response, status

from auth_service.api.dependencies import (
    get_auth_service,
    get_current_access_token,
    get_db_connection,
    get_rate_limiter,
)
from auth_service.core.rate_limiter import RateLimiter
from auth_service.core.settings import Settings, get_settings
from auth_service.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenPairResponse,
    UserResponse,
)
from auth_service.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
    limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> RegisterResponse:
    ip = _client_ip(request)
    await limiter.enforce(f"rate:register:{ip}:{payload.email}", settings.rate_limit_register)
    created = await auth_service.register(conn=conn, email=str(payload.email), password=payload.password)

    if created:
        return RegisterResponse(status="created", message="Registration accepted")
    response.status_code = status.HTTP_200_OK
    return RegisterResponse(status="ok", message="Registration accepted")


@router.post("/login", response_model=TokenPairResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> TokenPairResponse:
    ip = _client_ip(request)
    await limiter.enforce(f"rate:login:{ip}:{payload.email}", settings.rate_limit_login)
    tokens = await auth_service.login(
        conn=conn,
        email=str(payload.email),
        password=payload.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=ip,
    )
    return TokenPairResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> TokenPairResponse:
    tokens = await auth_service.refresh(
        conn=conn,
        refresh_token=payload.refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    return TokenPairResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    auth_service: AuthService = Depends(get_auth_service),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> Response:
    await auth_service.logout(conn=conn, refresh_token=payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def me(
    access_token: str = Depends(get_current_access_token),
    auth_service: AuthService = Depends(get_auth_service),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> UserResponse:
    user_id, email, is_active = await auth_service.get_user_by_access_token(conn, access_token)
    return UserResponse(id=str(user_id), email=email, is_active=is_active)
