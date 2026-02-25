from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg

from auth_service.core.exceptions import AuthenticationError, AuthorizationError
from auth_service.core.jwt import JWTManager
from auth_service.core.security import PasswordManager, RefreshTokenManager
from auth_service.repositories.sessions import SessionsRepository
from auth_service.repositories.users import UsersRepository


@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        users_repository: UsersRepository,
        sessions_repository: SessionsRepository,
        password_manager: PasswordManager,
        refresh_token_manager: RefreshTokenManager,
        jwt_manager: JWTManager,
        refresh_ttl_days: int,
    ) -> None:
        self._users = users_repository
        self._sessions = sessions_repository
        self._password_manager = password_manager
        self._refresh_token_manager = refresh_token_manager
        self._jwt_manager = jwt_manager
        self._refresh_ttl_days = refresh_ttl_days

    async def register(self, conn: asyncpg.Connection, email: str, password: str) -> bool:
        password_hash = self._password_manager.hash_password(password)

        try:
            async with conn.transaction():
                await self._users.create(conn, user_id=uuid4(), email=email, password_hash=password_hash)
            return True
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505":
                return False
            raise

    async def login(
        self,
        conn: asyncpg.Connection,
        email: str,
        password: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        user = await self._users.get_by_email(conn, email)
        if user is None or not user.is_active:
            raise AuthenticationError()

        if not self._password_manager.verify_password(password, user.password_hash):
            raise AuthenticationError()

        return await self._create_session_tokens(
            conn=conn,
            user_id=user.id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    async def refresh(
        self,
        conn: asyncpg.Connection,
        refresh_token: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        token_hash = self._refresh_token_manager.hash_token(refresh_token)
        session = await self._sessions.get_active_by_hash(conn, token_hash)
        if session is None:
            raise AuthorizationError("Invalid refresh token")

        user = await self._users.get_by_id(conn, session.user_id)
        if user is None or not user.is_active:
            raise AuthorizationError("Invalid refresh token")

        async with conn.transaction():
            await self._sessions.revoke_by_id(conn, session.id)
            return await self._create_session_tokens(
                conn=conn,
                user_id=user.id,
                user_agent=user_agent,
                ip_address=ip_address,
            )

    async def logout(self, conn: asyncpg.Connection, refresh_token: str) -> None:
        token_hash = self._refresh_token_manager.hash_token(refresh_token)
        await self._sessions.revoke_by_hash(conn, token_hash)

    async def get_user_by_access_token(self, conn: asyncpg.Connection, access_token: str) -> tuple[UUID, str, bool]:
        payload = self._jwt_manager.decode_access_token(access_token)
        try:
            user_id = UUID(payload["sub"])
        except ValueError as exc:
            raise AuthorizationError("Invalid token") from exc

        user = await self._users.get_by_id(conn, user_id)
        if user is None or not user.is_active:
            raise AuthorizationError("Invalid token")

        return user.id, user.email, user.is_active

    async def _create_session_tokens(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        refresh_token = self._refresh_token_manager.generate_token()
        refresh_token_hash = self._refresh_token_manager.hash_token(refresh_token)

        await self._sessions.create(
            conn=conn,
            session_id=uuid4(),
            user_id=user_id,
            token_hash=refresh_token_hash,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=self._refresh_token_manager.expires_at(self._refresh_ttl_days),
        )

        access_token, expires_in = self._jwt_manager.create_access_token(str(user_id))
        return TokenPair(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)
