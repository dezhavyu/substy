from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
import respx
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient, Response

from bff_gateway.core.settings import get_settings
from bff_gateway.main import create_app


class FakeRedis:
    async def eval(self, script, keys, key, window):
        return 1

    async def ping(self):
        return True

    async def aclose(self):
        return None


def _make_access_token() -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "roles": ["user"],
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.mark.asyncio
@respx.mock
async def test_login_sets_http_only_refresh_cookie_and_hides_refresh_token(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()
    respx.post("http://auth.test/auth/login").mock(
        return_value=Response(
            200,
            json={
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "token_type": "bearer",
                "expires_in": 900,
            },
        )
    )

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/auth/login",
                json={"email": "user@example.com", "password": "VeryStrongPassword123"},
            )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "access-1",
        "token_type": "bearer",
        "expires_in": 900,
    }
    set_cookie = response.headers.get("set-cookie", "")
    assert "refresh_token=refresh-1" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()


@pytest.mark.asyncio
@respx.mock
async def test_refresh_uses_cookie_and_rotates_refresh_cookie(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()
    captured = {}

    def handler(request):
        captured["body"] = request.content.decode("utf-8")
        captured["content_type"] = request.headers.get("content-type")
        return Response(
            200,
            json={
                "access_token": "access-2",
                "refresh_token": "refresh-2",
                "token_type": "bearer",
                "expires_in": 900,
            },
        )

    respx.post("http://auth.test/auth/refresh").mock(side_effect=handler)

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/auth/refresh", cookies={"refresh_token": "refresh-1"})

    assert response.status_code == 200
    assert captured["body"] == '{"refresh_token": "refresh-1"}'
    assert captured["content_type"] == "application/json"
    assert response.json() == {
        "access_token": "access-2",
        "token_type": "bearer",
        "expires_in": 900,
    }
    assert "refresh_token=refresh-2" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
@respx.mock
async def test_api_me_alias_proxies_to_auth_service(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()
    respx.get("http://auth.test/auth/me").mock(
        return_value=Response(200, json={"id": str(uuid4()), "email": "user@example.com", "is_active": True})
    )

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _make_access_token()
            response = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


@pytest.mark.asyncio
@respx.mock
async def test_logout_uses_cookie_token_and_clears_refresh_cookie(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()
    captured = {}

    def handler(request):
        captured["body"] = request.content.decode("utf-8")
        captured["content_length"] = request.headers.get("content-length")
        captured["content_type"] = request.headers.get("content-type")
        return Response(204)

    respx.post("http://auth.test/auth/logout").mock(side_effect=handler)

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/auth/logout",
                cookies={"refresh_token": "refresh-1"},
            )

    assert response.status_code == 204
    assert captured["body"] == '{"refresh_token": "refresh-1"}'
    assert captured["content_length"] == str(len(captured["body"]))
    assert captured["content_type"] == "application/json"
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "refresh_token=" in set_cookie
    assert "max-age=0" in set_cookie or "expires=" in set_cookie


@pytest.mark.asyncio
@respx.mock
async def test_refresh_quoted_empty_cookie_returns_401_without_upstream_call(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()
    upstream = respx.post("http://auth.test/auth/refresh").mock(return_value=Response(200, json={}))

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/auth/refresh", cookies={"refresh_token": '""'})

    assert response.status_code == 401
    assert upstream.call_count == 0
    assert response.headers.get("set-cookie") is None


@pytest.mark.asyncio
@respx.mock
async def test_refresh_short_cookie_maps_upstream_422_to_401_without_clearing_cookie(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()
    upstream = respx.post("http://auth.test/auth/refresh").mock(return_value=Response(422))

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/auth/refresh", cookies={"refresh_token": "short"})

    assert response.status_code == 401
    assert upstream.call_count == 1
    assert response.headers.get("set-cookie") is None


@pytest.mark.asyncio
@respx.mock
async def test_logout_quoted_empty_cookie_returns_204_without_upstream_call(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()
    upstream = respx.post("http://auth.test/auth/logout").mock(return_value=Response(204))

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/auth/logout", cookies={"refresh_token": '""'})

    assert response.status_code == 204
    assert upstream.call_count == 0


@pytest.mark.asyncio
@respx.mock
async def test_logout_short_cookie_maps_upstream_422_to_204_and_clears_cookie(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()
    upstream = respx.post("http://auth.test/auth/logout").mock(return_value=Response(422))

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/auth/logout", cookies={"refresh_token": "short"})

    assert response.status_code == 204
    assert upstream.call_count == 1
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "refresh_token=" in set_cookie
    assert "max-age=0" in set_cookie or "expires=" in set_cookie
