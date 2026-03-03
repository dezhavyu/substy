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


def make_token() -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "roles": ["user", "admin"],
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.mark.asyncio
@respx.mock
async def test_proxy_forwards_query_body_and_identity_headers(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()

    captured = {}

    def handler(request):
        query = request.url.query
        captured["query"] = query.decode("utf-8") if isinstance(query, bytes) else str(query)
        captured["body"] = request.content.decode("utf-8")
        captured["x_user_id"] = request.headers.get("x-user-id")
        captured["x_user_roles"] = request.headers.get("x-user-roles")
        return Response(200, json={"ok": True})

    respx.post("http://subs.test/subscriptions").mock(side_effect=handler)

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = make_token()
            response = await client.post(
                "/api/subscriptions?foo=bar",
                headers={"Authorization": f"Bearer {token}", "X-Request-Id": "req-1"},
                json={"topic_id": str(uuid4())},
            )

    assert response.status_code == 200
    assert captured["query"] == "foo=bar"
    assert "topic_id" in captured["body"]
    assert captured["x_user_id"]
    assert "admin" in (captured["x_user_roles"] or "")


@pytest.mark.asyncio
@respx.mock
async def test_subscribe_creates_notification_event(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()
    topic_id = str(uuid4())
    subscription_id = str(uuid4())
    captured = {}

    respx.post("http://subs.test/subscriptions").mock(
        return_value=Response(201, json={"id": subscription_id, "topic_id": topic_id, "is_active": True})
    )

    def notifications_handler(request):
        captured["body"] = request.content.decode("utf-8")
        captured["x_user_id"] = request.headers.get("x-user-id")
        return Response(201, json={"id": str(uuid4())})

    notifications_route = respx.post("http://notifs.test/notifications").mock(side_effect=notifications_handler)

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = make_token()
            response = await client.post(
                "/api/subscriptions",
                headers={"Authorization": f"Bearer {token}"},
                json={"topic_id": topic_id},
            )

    assert response.status_code == 201
    assert notifications_route.call_count == 1
    assert topic_id in (captured.get("body") or "")
    assert "subscription.subscribed" in (captured.get("body") or "")
    assert captured.get("x_user_id")


@pytest.mark.asyncio
@respx.mock
async def test_unsubscribe_creates_notification_event(monkeypatch):
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth.test")
    monkeypatch.setenv("SUBSCRIPTIONS_SERVICE_URL", "http://subs.test")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifs.test")
    get_settings.cache_clear()

    app = create_app()
    topic_id = str(uuid4())
    subscription_id = str(uuid4())
    captured = {}

    respx.get("http://subs.test/subscriptions/me").mock(
        return_value=Response(
            200,
            json={"items": [{"id": subscription_id, "topic_id": topic_id, "is_active": True}], "next_cursor": None},
        )
    )
    respx.delete(f"http://subs.test/subscriptions/{subscription_id}").mock(return_value=Response(204))

    def notifications_handler(request):
        captured["body"] = request.content.decode("utf-8")
        return Response(201, json={"id": str(uuid4())})

    notifications_route = respx.post("http://notifs.test/notifications").mock(side_effect=notifications_handler)

    async with LifespanManager(app):
        app.state.redis = FakeRedis()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = make_token()
            response = await client.delete(
                f"/api/subscriptions/{subscription_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert response.status_code == 204
    assert notifications_route.call_count == 1
    assert topic_id in (captured.get("body") or "")
    assert "subscription.unsubscribed" in (captured.get("body") or "")
