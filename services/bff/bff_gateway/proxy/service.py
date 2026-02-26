from fastapi import Request, Response

from bff_gateway.clients.downstream import ServiceClients, send_with_retries
from bff_gateway.core.settings import Settings
from bff_gateway.proxy.headers import filter_request_headers


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def proxy_request(
    request: Request,
    response: Response,
    *,
    clients: ServiceClients,
    service_name: str,
    base_path: str,
    settings: Settings,
    user_id: str | None,
    user_roles: set[str] | None,
):
    client = getattr(clients, service_name)
    headers = filter_request_headers(dict(request.headers))

    headers["X-Request-Id"] = getattr(request.state, "request_id", "")
    headers["X-Client-Ip"] = _client_ip(request)
    if user_id:
        headers["X-User-Id"] = user_id
    if user_roles is not None:
        headers["X-User-Roles"] = ",".join(sorted(user_roles))

    body = getattr(request.state, "cached_body", None)
    if body is None:
        body = await request.body()

    upstream = await send_with_retries(
        client=client,
        method=request.method,
        path=base_path,
        params=request.query_params,
        headers=headers,
        content=body,
        retries_get=settings.http_retries_get,
        service_name=service_name,
    )
    metrics = getattr(request.app.state, "metrics", None)
    if metrics and upstream.status_code >= 500:
        metrics.inc_downstream_error(service_name)

    response.status_code = upstream.status_code

    filtered_response_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in {"transfer-encoding", "connection", "content-length"}
    }

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=filtered_response_headers,
        media_type=upstream.headers.get("content-type"),
    )
