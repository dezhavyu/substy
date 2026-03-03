import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from bff_gateway.api.dependencies import get_clients, rate_limit_user
from bff_gateway.clients.downstream import ServiceClients, send_with_retries
from bff_gateway.core.settings import Settings, get_settings
from bff_gateway.proxy.headers import filter_request_headers
from bff_gateway.proxy.service import proxy_request
from bff_gateway.core.errors import ForbiddenError

router = APIRouter(tags=["subscriptions"])
logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _build_headers(request: Request, user_id: str, user_roles: set[str]) -> dict[str, str]:
    headers = filter_request_headers(dict(request.headers))
    headers["X-Request-Id"] = getattr(request.state, "request_id", "")
    headers["X-Client-Ip"] = _client_ip(request)
    headers["X-User-Id"] = user_id
    headers["X-User-Roles"] = ",".join(sorted(user_roles))
    return headers


async def _cached_body(request: Request) -> bytes:
    body = getattr(request.state, "cached_body", None)
    if body is not None:
        return body
    return await request.body()


def _filtered_upstream_headers(upstream_headers: Any) -> dict[str, str]:
    blocked = {"transfer-encoding", "connection", "content-length", "content-encoding"}
    return {k: v for k, v in upstream_headers.items() if k.lower() not in blocked}


def _passthrough_response(upstream_response: Any) -> Response:
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=_filtered_upstream_headers(upstream_response.headers),
        media_type=upstream_response.headers.get("content-type"),
    )


def _as_json_dict(raw: bytes) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _record_upstream_error(request: Request, service_name: str, status_code: int) -> None:
    metrics = getattr(request.app.state, "metrics", None)
    if metrics and status_code >= 500:
        metrics.inc_downstream_error(service_name)


async def _send_subscriptions_request(
    request: Request,
    clients: ServiceClients,
    settings: Settings,
    user_id: str,
    user_roles: set[str],
    path: str,
    method: str,
    body: bytes,
    params: Any,
) -> Any:
    return await send_with_retries(
        client=clients.subscriptions,
        method=method,
        path=path,
        params=params,
        headers=_build_headers(request, user_id, user_roles),
        content=body,
        retries_get=settings.http_retries_get,
        service_name="subscriptions",
    )


async def _notify_subscription_event(
    request: Request,
    clients: ServiceClients,
    settings: Settings,
    user_id: str,
    user_roles: set[str],
    *,
    topic_id: str,
    event_type: str,
    message: str,
    subscription_id: str | None = None,
) -> None:
    request_id = getattr(request.state, "request_id", "")
    idempotency_suffix = subscription_id or topic_id
    payload = {
        "topic_id": topic_id,
        "payload": {
            "event_type": event_type,
            "message": message,
            "topic_id": topic_id,
            "subscription_id": subscription_id,
        },
        "idempotency_key": f"bff:{event_type}:{idempotency_suffix}:{request_id}",
    }

    headers = _build_headers(request, user_id, user_roles)
    headers["Content-Type"] = "application/json"

    try:
        upstream = await send_with_retries(
            client=clients.notifications,
            method="POST",
            path="/notifications",
            params={},
            headers=headers,
            content=json.dumps(payload).encode("utf-8"),
            retries_get=settings.http_retries_get,
            service_name="notifications",
        )
        _record_upstream_error(request, "notifications", upstream.status_code)
        if upstream.status_code not in {200, 201}:
            logger.warning(
                "Subscription notification dispatch failed",
                extra={"status_code": upstream.status_code, "event_type": event_type, "topic_id": topic_id},
            )
    except Exception:
        logger.exception(
            "Subscription notification dispatch error",
            extra={"event_type": event_type, "topic_id": topic_id},
        )


async def _find_topic_id_by_subscription_id(
    request: Request,
    clients: ServiceClients,
    settings: Settings,
    user_id: str,
    user_roles: set[str],
    subscription_id: str,
) -> str | None:
    cursor: str | None = None

    for _ in range(20):
        params: dict[str, str] = {"limit": "500"}
        if cursor:
            params["cursor"] = cursor

        upstream = await _send_subscriptions_request(
            request=request,
            clients=clients,
            settings=settings,
            user_id=user_id,
            user_roles=user_roles,
            path="/subscriptions/me",
            method="GET",
            body=b"",
            params=params,
        )
        _record_upstream_error(request, "subscriptions", upstream.status_code)
        if upstream.status_code != 200:
            return None

        payload = _as_json_dict(upstream.content)
        if payload is None:
            return None

        items = payload.get("items")
        if not isinstance(items, list):
            return None

        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("id")) != subscription_id:
                continue
            topic_id = item.get("topic_id")
            if isinstance(topic_id, str) and topic_id:
                return topic_id
            return None

        next_cursor = payload.get("next_cursor") or payload.get("nextCursor")
        if not isinstance(next_cursor, str) or not next_cursor:
            return None
        cursor = next_cursor

    return None


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
    user_id = str(identity.user_id)
    request_body = await _cached_body(request)

    upstream = await _send_subscriptions_request(
        request=request,
        clients=clients,
        settings=settings,
        user_id=user_id,
        user_roles=identity.roles,
        path="/subscriptions",
        method=request.method,
        body=request_body,
        params=request.query_params,
    )
    _record_upstream_error(request, "subscriptions", upstream.status_code)

    if upstream.status_code in {200, 201}:
        payload = _as_json_dict(upstream.content)
        topic_id = payload.get("topic_id") if isinstance(payload, dict) else None
        subscription_id = payload.get("id") if isinstance(payload, dict) else None
        if isinstance(topic_id, str) and topic_id:
            await _notify_subscription_event(
                request=request,
                clients=clients,
                settings=settings,
                user_id=user_id,
                user_roles=identity.roles,
                topic_id=topic_id,
                event_type="subscription.subscribed",
                message="You subscribed to topic updates.",
                subscription_id=subscription_id if isinstance(subscription_id, str) else None,
            )

    return _passthrough_response(upstream)


@router.delete("/subscriptions/{subscription_id}")
async def unsubscribe(
    subscription_id: str,
    request: Request,
    response: Response,
    identity=Depends(rate_limit_user),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    user_id = str(identity.user_id)
    topic_id = await _find_topic_id_by_subscription_id(
        request=request,
        clients=clients,
        settings=settings,
        user_id=user_id,
        user_roles=identity.roles,
        subscription_id=subscription_id,
    )

    upstream = await _send_subscriptions_request(
        request=request,
        clients=clients,
        settings=settings,
        user_id=user_id,
        user_roles=identity.roles,
        path=f"/subscriptions/{subscription_id}",
        method=request.method,
        body=await _cached_body(request),
        params=request.query_params,
    )
    _record_upstream_error(request, "subscriptions", upstream.status_code)

    if upstream.status_code == 204 and isinstance(topic_id, str) and topic_id:
        await _notify_subscription_event(
            request=request,
            clients=clients,
            settings=settings,
            user_id=user_id,
            user_roles=identity.roles,
            topic_id=topic_id,
            event_type="subscription.unsubscribed",
            message="You unsubscribed from topic updates.",
            subscription_id=subscription_id,
        )

    return _passthrough_response(upstream)


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
