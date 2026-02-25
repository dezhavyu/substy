import pytest
from uuid import uuid4


@pytest.mark.asyncio
async def test_register_and_login_flow(client):
    email = f"{uuid4()}@example.com"
    password = "VeryStrongPassword123"
    register_resp = await client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert register_resp.status_code in (200, 201)

    login_resp = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200

    body = login_resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
