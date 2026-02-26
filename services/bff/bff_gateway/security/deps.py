from fastapi import Depends, Header, Request

from bff_gateway.core.errors import ForbiddenError, UnauthorizedError
from bff_gateway.security.jwt import Identity, JWTVerifier


def get_jwt_verifier(request: Request) -> JWTVerifier:
    return request.app.state.jwt_verifier


def get_current_identity(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    verifier: JWTVerifier = Depends(get_jwt_verifier),
) -> Identity:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError()

    token = authorization.removeprefix("Bearer ").strip()
    identity = verifier.verify(token)
    request.state.user_id = str(identity.user_id)
    request.state.user_roles = identity.roles
    return identity


def require_admin(identity: Identity = Depends(get_current_identity)) -> Identity:
    if "admin" not in identity.roles:
        raise ForbiddenError()
    return identity
