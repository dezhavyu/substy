from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from bff_gateway.core.errors import UnauthorizedError
from bff_gateway.core.settings import Settings


@dataclass(slots=True)
class Identity:
    user_id: UUID
    roles: set[str]


class JWTVerifier:
    def __init__(self, settings: Settings) -> None:
        self._algorithm = settings.jwt_algorithm
        self._issuer = settings.jwt_issuer
        self._audience = settings.jwt_audience

        if self._algorithm.startswith("RS"):
            if not settings.jwt_public_key:
                raise ValueError("JWT public key is required for RS algorithms")
            self._key = settings.jwt_public_key.replace("\\n", "\n")
        else:
            self._key = settings.jwt_secret

    def verify(self, token: str) -> Identity:
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._key,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
            )
        except InvalidTokenError as exc:
            raise UnauthorizedError("Invalid access token") from exc

        sub = payload.get("sub")
        if not sub:
            raise UnauthorizedError("Invalid access token")

        try:
            user_id = UUID(str(sub))
        except ValueError as exc:
            raise UnauthorizedError("Invalid access token") from exc

        raw_roles = payload.get("roles", [])
        if isinstance(raw_roles, str):
            roles = {role.strip().lower() for role in raw_roles.split(",") if role.strip()}
        elif isinstance(raw_roles, list):
            roles = {str(role).strip().lower() for role in raw_roles if str(role).strip()}
        else:
            roles = set()

        return Identity(user_id=user_id, roles=roles)
