from datetime import datetime
from uuid import UUID

import asyncpg

from auth_service.domain.models import Session


class SessionsRepository:
    async def create(
        self,
        conn: asyncpg.Connection,
        session_id: UUID,
        user_id: UUID,
        token_hash: str,
        user_agent: str | None,
        ip_address: str | None,
        expires_at: datetime,
    ) -> Session:
        row = await conn.fetchrow(
            """
            INSERT INTO auth.sessions (
                id, user_id, token_hash, user_agent, ip_address, expires_at, revoked_at, created_at
            ) VALUES ($1, $2, $3, $4, $5::inet, $6, NULL, now())
            RETURNING id, user_id, token_hash, user_agent, ip_address, expires_at, revoked_at, created_at
            """,
            session_id,
            user_id,
            token_hash,
            user_agent,
            ip_address,
            expires_at,
        )
        return self._to_model(row)

    async def get_active_by_hash(self, conn: asyncpg.Connection, token_hash: str) -> Session | None:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, token_hash, user_agent, ip_address, expires_at, revoked_at, created_at
            FROM auth.sessions
            WHERE token_hash = $1
              AND revoked_at IS NULL
              AND expires_at > now()
            """,
            token_hash,
        )
        return self._to_model(row) if row else None

    async def revoke_by_hash(self, conn: asyncpg.Connection, token_hash: str) -> None:
        await conn.execute(
            """
            UPDATE auth.sessions
            SET revoked_at = now()
            WHERE token_hash = $1
              AND revoked_at IS NULL
            """,
            token_hash,
        )

    async def revoke_by_id(self, conn: asyncpg.Connection, session_id: UUID) -> None:
        await conn.execute(
            """
            UPDATE auth.sessions
            SET revoked_at = now()
            WHERE id = $1
              AND revoked_at IS NULL
            """,
            session_id,
        )

    @staticmethod
    def _to_model(row: asyncpg.Record) -> Session:
        return Session(
            id=row["id"],
            user_id=row["user_id"],
            token_hash=row["token_hash"],
            user_agent=row["user_agent"],
            ip_address=str(row["ip_address"]) if row["ip_address"] else None,
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            created_at=row["created_at"],
        )
