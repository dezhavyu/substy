from uuid import uuid4

import pytest


def _admin_headers() -> dict[str, str]:
    return {
        "X-User-Id": str(uuid4()),
        "X-User-Roles": "admin",
    }


def _user_headers(user_id: str) -> dict[str, str]:
    return {
        "X-User-Id": user_id,
        "X-User-Roles": "user",
    }


@pytest.mark.asyncio
async def test_create_topic_admin(client):
    payload = {"key": f"news.{uuid4().hex[:8]}", "name": "News", "description": "Announcements"}
    response = await client.post("/topics", json=payload, headers=_admin_headers())

    assert response.status_code == 201
    body = response.json()
    assert body["key"] == payload["key"]
    assert body["name"] == payload["name"]


@pytest.mark.asyncio
async def test_subscribe_and_unsubscribe(client):
    create_resp = await client.post(
        "/topics",
        json={"key": f"system.{uuid4().hex[:8]}", "name": "System", "description": None},
        headers=_admin_headers(),
    )
    topic_id = create_resp.json()["id"]

    user_id = str(uuid4())
    subscribe_resp = await client.post(
        "/subscriptions",
        json={"topic_id": topic_id},
        headers=_user_headers(user_id),
    )
    assert subscribe_resp.status_code == 201
    subscription_id = subscribe_resp.json()["id"]

    second_resp = await client.post(
        "/subscriptions",
        json={"topic_id": topic_id},
        headers=_user_headers(user_id),
    )
    assert second_resp.status_code == 200
    assert second_resp.json()["id"] == subscription_id

    delete_resp = await client.delete(f"/subscriptions/{subscription_id}", headers=_user_headers(user_id))
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_internal_subscribers_cursor_pagination(client):
    create_resp = await client.post(
        "/topics",
        json={"key": f"fanout.{uuid4().hex[:8]}", "name": "Fanout", "description": None},
        headers=_admin_headers(),
    )
    topic_id = create_resp.json()["id"]

    users = [str(uuid4()) for _ in range(5)]
    for user_id in users:
        response = await client.post(
            "/subscriptions",
            json={"topic_id": topic_id},
            headers=_user_headers(user_id),
        )
        assert response.status_code in (200, 201)

    first_page = await client.get(f"/internal/topics/{topic_id}/subscribers?limit=2")
    assert first_page.status_code == 200
    first_body = first_page.json()

    second_page = await client.get(
        f"/internal/topics/{topic_id}/subscribers",
        params={"limit": 2, "cursor": first_body["next_cursor"]},
    )
    assert second_page.status_code == 200
    second_body = second_page.json()

    first_ids = [x["user_id"] for x in first_body["items"]]
    second_ids = [x["user_id"] for x in second_body["items"]]

    assert len(first_ids) == 2
    assert len(second_ids) == 2
    assert set(first_ids).isdisjoint(set(second_ids))
    assert first_body["next_cursor"] is not None
