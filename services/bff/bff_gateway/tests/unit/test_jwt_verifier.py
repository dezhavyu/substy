from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from bff_gateway.core.errors import UnauthorizedError
from bff_gateway.core.settings import Settings
from bff_gateway.security.jwt import JWTVerifier


def _make_token(secret: str, sub: str, exp_seconds: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "iss": "auth-service",
        "aud": "substy",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_seconds)).timestamp()),
        "roles": ["user", "admin"],
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_valid_jwt_verification():
    settings = Settings()
    verifier = JWTVerifier(settings)
    user_id = str(uuid4())
    token = _make_token(settings.jwt_secret, user_id, 300)

    identity = verifier.verify(token)
    assert str(identity.user_id) == user_id
    assert "admin" in identity.roles


def test_expired_jwt_rejected():
    settings = Settings()
    verifier = JWTVerifier(settings)
    token = _make_token(settings.jwt_secret, str(uuid4()), -1)

    with pytest.raises(UnauthorizedError):
        verifier.verify(token)


def test_invalid_signature_rejected():
    settings = Settings()
    verifier = JWTVerifier(settings)
    token = _make_token("wrong-secret-at-least-32-bytes-long", str(uuid4()), 300)

    with pytest.raises(UnauthorizedError):
        verifier.verify(token)
