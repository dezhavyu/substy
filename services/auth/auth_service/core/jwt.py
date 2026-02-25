from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError

from auth_service.core.exceptions import AuthorizationError
from auth_service.core.settings import Settings


class JWTManager:
    def __init__(self, settings: Settings) -> None:
        self._algorithm = settings.jwt_algorithm
        self._issuer = settings.jwt_issuer
        self._audience = settings.jwt_audience
        self._access_ttl = timedelta(minutes=settings.jwt_access_token_ttl_minutes)

        self._encode_key: str = settings.jwt_secret
        self._decode_key: str = settings.jwt_secret
        if self._algorithm.startswith("RS"):
            if not settings.jwt_private_key or not settings.jwt_public_key:
                raise ValueError("JWT private/public keys are required for RS algorithms")
            self._encode_key = settings.jwt_private_key.replace("\\n", "\n")
            self._decode_key = settings.jwt_public_key.replace("\\n", "\n")

    def create_access_token(self, subject: str, extra_claims: dict[str, Any] | None = None) -> tuple[str, int]:
        now = datetime.now(tz=timezone.utc)
        expires = now + self._access_ttl
        claims: dict[str, Any] = {
            "sub": subject,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "type": "access",
        }
        if extra_claims:
            claims.update(extra_claims)

        token = jwt.encode(claims, self._encode_key, algorithm=self._algorithm)
        return token, int(self._access_ttl.total_seconds())

    def decode_access_token(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._decode_key,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
            )
        except InvalidTokenError as exc:
            raise AuthorizationError("Invalid token") from exc

        if payload.get("type") != "access":
            raise AuthorizationError("Invalid token")

        return payload
