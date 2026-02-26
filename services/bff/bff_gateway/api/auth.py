from fastapi import APIRouter, Depends, Request, Response

from bff_gateway.api.dependencies import get_clients, rate_limit_auth, rate_limit_user
from bff_gateway.clients.downstream import ServiceClients
from bff_gateway.core.settings import Settings, get_settings
from bff_gateway.proxy.service import proxy_request

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(
    request: Request,
    response: Response,
    _: None = Depends(rate_limit_auth),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(
        request,
        response,
        clients=clients,
        service_name="auth",
        base_path="/auth/register",
        settings=settings,
        user_id=None,
        user_roles=None,
    )


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    _: None = Depends(rate_limit_auth),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(
        request,
        response,
        clients=clients,
        service_name="auth",
        base_path="/auth/login",
        settings=settings,
        user_id=None,
        user_roles=None,
    )


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(
        request,
        response,
        clients=clients,
        service_name="auth",
        base_path="/auth/refresh",
        settings=settings,
        user_id=None,
        user_roles=None,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(
        request,
        response,
        clients=clients,
        service_name="auth",
        base_path="/auth/logout",
        settings=settings,
        user_id=None,
        user_roles=None,
    )


@router.get("/me")
async def me(
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(
        request,
        response,
        clients=clients,
        service_name="auth",
        base_path="/auth/me",
        settings=settings,
        user_id=str(identity.user_id),
        user_roles=identity.roles,
    )
