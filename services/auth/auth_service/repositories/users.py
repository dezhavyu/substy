from datetime import datetime
from uuid import UUID

import asyncpg

from auth_service.domain.models import User


class UsersRepository:
    async def create(self, conn: asyncpg.Connection, user_id: UUID, email: str, password_hash: str) -> User:
        row = await conn.fetchrow(
            """
            INSERT INTO auth.users (id, email, password_hash, is_active, created_at)
            VALUES ($1, $2, $3, TRUE, now())
            RETURNING id, email, password_hash, is_active, created_at
            """,
            user_id,
            email,
            password_hash,
        )
        return self._to_model(row)

    async def get_by_email(self, conn: asyncpg.Connection, email: str) -> User | None:
        row = await conn.fetchrow(
            """
            SELECT id, email, password_hash, is_active, created_at
            FROM auth.users
            WHERE email = $1
            """,
            email,
        )
        return self._to_model(row) if row else None

    async def get_by_id(self, conn: asyncpg.Connection, user_id: UUID) -> User | None:
        row = await conn.fetchrow(
            """
            SELECT id, email, password_hash, is_active, created_at
            FROM auth.users
            WHERE id = $1
            """,
            user_id,
        )
        return self._to_model(row) if row else None

    @staticmethod
    def _to_model(row: asyncpg.Record) -> User:
        return User(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )
