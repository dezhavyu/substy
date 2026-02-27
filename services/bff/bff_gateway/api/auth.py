import json
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from bff_gateway.api.dependencies import get_clients, rate_limit_auth, rate_limit_user
from bff_gateway.clients.downstream import ServiceClients, send_with_retries
from bff_gateway.core.settings import Settings, get_settings
from bff_gateway.proxy.headers import filter_request_headers
from bff_gateway.proxy.service import proxy_request

router = APIRouter(tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _build_headers(request: Request) -> dict[str, str]:
    headers = filter_request_headers(dict(request.headers))
    headers["X-Request-Id"] = getattr(request.state, "request_id", "")
    headers["X-Client-Ip"] = _client_ip(request)
    return headers


async def _cached_body(request: Request) -> bytes:
    body = getattr(request.state, "cached_body", None)
    if body is not None:
        return body
    return await request.body()


def _filtered_upstream_headers(upstream_headers: Any) -> dict[str, str]:
    blocked = {"transfer-encoding", "connection", "content-length", "set-cookie", "content-encoding"}
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


def _normalize_refresh_token(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = unquote(value).strip().strip('"').strip()
    if not normalized:
        return None
    return normalized


def _refresh_from_body(raw: bytes) -> str | None:
    payload = _as_json_dict(raw)
    if payload is None:
        return None
    return _normalize_refresh_token(payload.get("refresh_token"))


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_cookie_max_age_seconds,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        domain=settings.parsed_refresh_cookie_domain,
        path=settings.refresh_cookie_path,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        domain=settings.parsed_refresh_cookie_domain,
        path=settings.refresh_cookie_path,
    )


def _record_auth_upstream_error(request: Request, status_code: int) -> None:
    metrics = getattr(request.app.state, "metrics", None)
    if metrics and status_code >= 500:
        metrics.inc_downstream_error("auth")


def _is_invalid_refresh_token_status(status_code: int) -> bool:
    return status_code in {400, 401, 404, 409, 410, 422}


def _unauthorized_response(
    request: Request,
    settings: Settings,
    message: str,
    *,
    clear_refresh_cookie: bool = False,
) -> JSONResponse:
    response = JSONResponse(
        status_code=401,
        content={
            "code": "unauthorized",
            "message": message,
            "request_id": getattr(request.state, "request_id", ""),
        },
    )
    if clear_refresh_cookie:
        _clear_refresh_cookie(response, settings)
    return response


async def _send_auth_request(
    request: Request,
    clients: ServiceClients,
    settings: Settings,
    path: str,
    body: bytes,
) -> Any:
    headers = _build_headers(request)
    if body and not any(key.lower() == "content-type" for key in headers):
        headers["Content-Type"] = "application/json"

    return await send_with_retries(
        client=clients.auth,
        method=request.method,
        path=path,
        params=request.query_params,
        headers=headers,
        content=body,
        retries_get=settings.http_retries_get,
        service_name="auth",
    )


@router.post("/auth/register")
@router.post("/api/auth/register")
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


@router.post("/auth/login")
@router.post("/api/auth/login")
async def login(
    request: Request,
    _: None = Depends(rate_limit_auth),
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    upstream = await _send_auth_request(
        request=request,
        clients=clients,
        settings=settings,
        path="/auth/login",
        body=await _cached_body(request),
    )
    _record_auth_upstream_error(request, upstream.status_code)

    payload = _as_json_dict(upstream.content)
    if payload is None:
        return _passthrough_response(upstream)

    refresh_token = payload.pop("refresh_token", None)
    if not isinstance(refresh_token, str) or not refresh_token:
        return _passthrough_response(upstream)

    response = JSONResponse(
        content=payload,
        status_code=upstream.status_code,
        headers=_filtered_upstream_headers(upstream.headers),
    )
    _set_refresh_cookie(response, refresh_token, settings)
    return response


@router.post("/auth/refresh")
@router.post("/api/auth/refresh")
async def refresh(
    request: Request,
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    request_body = await _cached_body(request)
    refresh_token = _normalize_refresh_token(request.cookies.get(settings.refresh_cookie_name)) or _refresh_from_body(
        request_body
    )
    if not refresh_token:
        return _unauthorized_response(request, settings, "Missing refresh token")

    upstream = await _send_auth_request(
        request=request,
        clients=clients,
        settings=settings,
        path="/auth/refresh",
        body=json.dumps({"refresh_token": refresh_token}).encode("utf-8"),
    )
    _record_auth_upstream_error(request, upstream.status_code)

    if _is_invalid_refresh_token_status(upstream.status_code):
        return _unauthorized_response(request, settings, "Invalid refresh token")

    payload = _as_json_dict(upstream.content)
    if payload is None:
        return _passthrough_response(upstream)

    new_refresh_token = payload.pop("refresh_token", None)
    if not isinstance(new_refresh_token, str) or not new_refresh_token:
        return _passthrough_response(upstream)

    response = JSONResponse(
        content=payload,
        status_code=upstream.status_code,
        headers=_filtered_upstream_headers(upstream.headers),
    )
    _set_refresh_cookie(response, new_refresh_token, settings)
    return response


@router.post("/auth/logout")
@router.post("/api/auth/logout")
async def logout(
    request: Request,
    clients: ServiceClients = Depends(get_clients),
    settings: Settings = Depends(get_settings),
):
    request_body = await _cached_body(request)
    refresh_token = _normalize_refresh_token(request.cookies.get(settings.refresh_cookie_name)) or _refresh_from_body(
        request_body
    )
    if not refresh_token:
        response = Response(status_code=204)
        _clear_refresh_cookie(response, settings)
        return response

    upstream = await _send_auth_request(
        request=request,
        clients=clients,
        settings=settings,
        path="/auth/logout",
        body=json.dumps({"refresh_token": refresh_token}).encode("utf-8"),
    )
    _record_auth_upstream_error(request, upstream.status_code)

    if _is_invalid_refresh_token_status(upstream.status_code):
        response = Response(status_code=204)
        _clear_refresh_cookie(response, settings)
        return response

    response = _passthrough_response(upstream)
    _clear_refresh_cookie(response, settings)
    return response


@router.get("/auth/me")
@router.get("/api/auth/me")
@router.get("/api/me")
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
