from __future__ import annotations

import hashlib
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class GrantManager:
    MAX_TTL = 86400

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init()

    def _init(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS grants (
                id          TEXT PRIMARY KEY,
                key_id      TEXT NOT NULL,
                grantor     TEXT NOT NULL,
                grantee     TEXT NOT NULL,
                ttl_seconds INTEGER NOT NULL,
                created_at  INTEGER NOT NULL,
                expires_at  INTEGER NOT NULL,
                jwt_hash    TEXT NOT NULL,
                used_at     INTEGER,
                revoked     INTEGER DEFAULT 0
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_grants_expires ON grants(expires_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_grants_grantee ON grants(grantee)"
        )
        conn.commit()
        conn.close()

    def create(
        self,
        key_id: str,
        grantor: str,
        grantee: str,
        ttl_seconds: int,
        jwt_hash: str,
    ) -> str:
        ttl_seconds = min(ttl_seconds, self.MAX_TTL)
        now = int(time.time())
        grant_id = str(uuid.uuid4())
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO grants "
            "(id, key_id, grantor, grantee, ttl_seconds, created_at, expires_at, jwt_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (grant_id, key_id, grantor, grantee, ttl_seconds, now,
             now + ttl_seconds, jwt_hash),
        )
        conn.commit()
        conn.close()
        return grant_id

    def is_valid(self, grant_id: str) -> bool:
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT expires_at, revoked FROM grants WHERE id = ?",
            (grant_id,),
        ).fetchone()
        conn.close()
        return row is not None and not row[1] and row[0] >= int(time.time())

    def mark_used(self, grant_id: str) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE grants SET used_at = ? WHERE id = ?",
            (int(time.time()), grant_id),
        )
        conn.commit()
        conn.close()

    def revoke(self, grant_id: str) -> bool:
        conn = sqlite3.connect(self._db_path)
        cursor = conn.execute(
            "UPDATE grants SET revoked = 1 WHERE id = ?", (grant_id,),
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def list_active(self, grantee: str | None = None) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        now = int(time.time())
        if grantee:
            rows = conn.execute(
                "SELECT * FROM grants "
                "WHERE grantee = ? AND revoked = 0 AND expires_at > ? "
                "ORDER BY created_at DESC",
                (grantee, now),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM grants "
                "WHERE revoked = 0 AND expires_at > ? "
                "ORDER BY created_at DESC",
                (now,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def hash_jwt(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()[:16]
