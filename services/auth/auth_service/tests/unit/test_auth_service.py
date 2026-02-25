from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from auth_service.core.exceptions import AuthenticationError, AuthorizationError
from auth_service.core.jwt import JWTManager
from auth_service.core.security import PasswordManager, RefreshTokenManager
from auth_service.core.settings import Settings
from auth_service.domain.models import Session, User
from auth_service.services.auth import AuthService


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def transaction(self):
        return FakeTransaction()


class FakeUsersRepository:
    def __init__(self):
        self.users_by_email: dict[str, User] = {}
        self.users_by_id: dict[str, User] = {}

    async def create(self, conn, user_id, email, password_hash):
        if email in self.users_by_email:
            class DuplicateError(Exception):
                sqlstate = "23505"

            raise DuplicateError()
        user = User(id=user_id, email=email, password_hash=password_hash, is_active=True, created_at=datetime.now(timezone.utc))
        self.users_by_email[email] = user
        self.users_by_id[str(user_id)] = user
        return user

    async def get_by_email(self, conn, email):
        return self.users_by_email.get(email)

    async def get_by_id(self, conn, user_id):
        return self.users_by_id.get(str(user_id))


class FakeSessionsRepository:
    def __init__(self):
        self.sessions: dict[str, Session] = {}

    async def create(self, conn, session_id, user_id, token_hash, user_agent, ip_address, expires_at):
        session = Session(
            id=session_id,
            user_id=user_id,
            token_hash=token_hash,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
            revoked_at=None,
            created_at=datetime.now(timezone.utc),
        )
        self.sessions[token_hash] = session
        return session

    async def get_active_by_hash(self, conn, token_hash):
        session = self.sessions.get(token_hash)
        if not session or session.revoked_at or session.expires_at <= datetime.now(timezone.utc):
            return None
        return session

    async def revoke_by_hash(self, conn, token_hash):
        session = self.sessions.get(token_hash)
        if session:
            session.revoked_at = datetime.now(timezone.utc)

    async def revoke_by_id(self, conn, session_id):
        for session in self.sessions.values():
            if session.id == session_id:
                session.revoked_at = datetime.now(timezone.utc)
                break


def build_service():
    settings = Settings()
    users = FakeUsersRepository()
    sessions = FakeSessionsRepository()
    service = AuthService(
        users_repository=users,
        sessions_repository=sessions,
        password_manager=PasswordManager(),
        refresh_token_manager=RefreshTokenManager(settings.refresh_token_pepper),
        jwt_manager=JWTManager(settings),
        refresh_ttl_days=settings.jwt_refresh_token_ttl_days,
    )
    return service, users, sessions


@pytest.mark.asyncio
async def test_register_is_idempotent():
    service, _, _ = build_service()
    conn = FakeConnection()

    created_first = await service.register(conn, "u@example.com", "StrongPassword123")
    created_second = await service.register(conn, "u@example.com", "StrongPassword123")

    assert created_first is True
    assert created_second is False


@pytest.mark.asyncio
async def test_login_returns_tokens_for_valid_credentials():
    service, _, _ = build_service()
    conn = FakeConnection()

    await service.register(conn, "u@example.com", "StrongPassword123")
    tokens = await service.login(conn, "u@example.com", "StrongPassword123", "pytest", "127.0.0.1")

    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.expires_in == 900


@pytest.mark.asyncio
async def test_login_rejects_invalid_password():
    service, _, _ = build_service()
    conn = FakeConnection()

    await service.register(conn, "u@example.com", "StrongPassword123")

    with pytest.raises(AuthenticationError):
        await service.login(conn, "u@example.com", "bad-password", "pytest", "127.0.0.1")


@pytest.mark.asyncio
async def test_refresh_rotates_session():
    service, _, sessions = build_service()
    conn = FakeConnection()

    await service.register(conn, "u@example.com", "StrongPassword123")
    tokens = await service.login(conn, "u@example.com", "StrongPassword123", "pytest", "127.0.0.1")

    old_hash = RefreshTokenManager(Settings().refresh_token_pepper).hash_token(tokens.refresh_token)
    refreshed = await service.refresh(conn, tokens.refresh_token, "pytest", "127.0.0.1")

    assert refreshed.refresh_token != tokens.refresh_token
    assert sessions.sessions[old_hash].revoked_at is not None


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_token():
    service, _, _ = build_service()

    with pytest.raises(AuthorizationError):
        await service.refresh(FakeConnection(), "bad-refresh-token", "pytest", "127.0.0.1")
