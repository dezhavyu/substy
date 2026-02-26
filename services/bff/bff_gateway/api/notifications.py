from fastapi import APIRouter, Depends, Request, Response

from bff_gateway.api.dependencies import get_clients, rate_limit_user
from bff_gateway.clients.downstream import ServiceClients
from bff_gateway.core.settings import Settings, get_settings
from bff_gateway.proxy.service import proxy_request

router = APIRouter(tags=["notifications"])


@router.post("/notifications")
async def create_notification(
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(request, response, clients=clients, service_name="notifications", base_path="/notifications", settings=settings, user_id=str(identity.user_id), user_roles=identity.roles)


@router.get("/notifications/{notification_id}")
async def get_notification(
    notification_id: str,
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(request, response, clients=clients, service_name="notifications", base_path=f"/notifications/{notification_id}", settings=settings, user_id=str(identity.user_id), user_roles=identity.roles)


@router.get("/notifications/me")
async def list_my_notifications(
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(request, response, clients=clients, service_name="notifications", base_path="/notifications/me", settings=settings, user_id=str(identity.user_id), user_roles=identity.roles)
