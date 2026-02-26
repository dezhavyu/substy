from fastapi import APIRouter, Depends, Request, Response

from bff_gateway.api.dependencies import get_clients, rate_limit_user
from bff_gateway.clients.downstream import ServiceClients
from bff_gateway.core.settings import Settings, get_settings
from bff_gateway.proxy.service import proxy_request
from bff_gateway.core.errors import ForbiddenError

router = APIRouter(tags=["subscriptions"])


@router.get("/topics")
async def topics(
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(request, response, clients=clients, service_name="subscriptions", base_path="/topics", settings=settings, user_id=str(identity.user_id), user_roles=identity.roles)


@router.get("/topics/{topic_id}")
async def topic_by_id(
    topic_id: str,
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(request, response, clients=clients, service_name="subscriptions", base_path=f"/topics/{topic_id}", settings=settings, user_id=str(identity.user_id), user_roles=identity.roles)


@router.post("/topics")
async def create_topic(
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    if "admin" not in identity.roles:
        raise ForbiddenError()
    return await proxy_request(request, response, clients=clients, service_name="subscriptions", base_path="/topics", settings=settings, user_id=str(identity.user_id), user_roles=identity.roles)


@router.get("/subscriptions/me")
async def my_subscriptions(
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(request, response, clients=clients, service_name="subscriptions", base_path="/subscriptions/me", settings=settings, user_id=str(identity.user_id), user_roles=identity.roles)


@router.post("/subscriptions")
async def subscribe(
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(request, response, clients=clients, service_name="subscriptions", base_path="/subscriptions", settings=settings, user_id=str(identity.user_id), user_roles=identity.roles)


@router.delete("/subscriptions/{subscription_id}")
async def unsubscribe(
    subscription_id: str,
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(request, response, clients=clients, service_name="subscriptions", base_path=f"/subscriptions/{subscription_id}", settings=settings, user_id=str(identity.user_id), user_roles=identity.roles)


@router.patch("/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    return await proxy_request(request, response, clients=clients, service_name="subscriptions", base_path=f"/subscriptions/{subscription_id}", settings=settings, user_id=str(identity.user_id), user_roles=identity.roles)
