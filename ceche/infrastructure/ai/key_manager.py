from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ceche.infrastructure.ai.security.vault import CredentialVault


@dataclass
class StoredKey:
    key_id: str
    provider: str
    label: str
    created_at: int
    expires_at: int | None
    created_by: str
    revoked: bool = False


def parse_expiry(value: str) -> int | None:
    value = value.strip().lower()
    if value in ("forever", "never", "none", "0"):
        return None
    multipliers: dict[str, int] = {
        "s": 1, "m": 60, "h": 3600, "d": 86400,
        "w": 604800, "mo": 2592000, "y": 31536000,
    }
    import re
    match = re.match(r"(\d+)\s*(s|m|h|d|w|mo|y)?", value)
    if match:
        num = int(match.group(1))
        unit = match.group(2) or "d"
        return num * multipliers.get(unit, 86400)
    return None  # forever


class KeyManager:
    def __init__(self, db_path: str | None = None) -> None:
        self._vault = CredentialVault(db_path=db_path)

    def add(
        self, provider: str, key: str, label: str = "",
        expiry: str = "forever", created_by: str = "user",
    ) -> dict[str, Any]:
        ttl = parse_expiry(expiry)
        now = int(time.time())
        expires_at = now + ttl if ttl else None
        ttl_str = str(ttl) if ttl else "forever"
        key_id = self._vault.store_key(key, provider, label, created_by, expires_at=expires_at)
        return {
            "key_id": key_id,
            "provider": provider,
            "label": label,
            "expiry": ttl_str,
            "created_at": now,
        }

    def get_key(self, key_id: str) -> str | None:
        return self._vault.get_key(key_id)

    def _get_ttl(self, key_id: str) -> int | None:
        return None

    def list_keys(self) -> list[dict[str, Any]]:
        import sqlite3
        conn = sqlite3.connect(self._vault._db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, provider, label, created_at, created_by, revoked "
            "FROM keys ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def remove(self, key_id: str) -> bool:
        return self._vault.revoke_key(key_id)

    def list_grants(self, grantee: str | None = None) -> list[dict[str, Any]]:
        return self._vault.list_grants(grantee=grantee)

    def get_active_key(self, provider: str) -> str | None:
        import sqlite3
        now = int(time.time())
        conn = sqlite3.connect(self._vault._db_path)
        row = conn.execute(
            "SELECT id, expires_at FROM keys "
            "WHERE provider = ? AND revoked = 0 "
            "ORDER BY rowid DESC LIMIT 1",
            (provider,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        expires = row[1]
        if expires is not None and expires < now:
            self._vault.revoke_key(row[0])
            return None
        return self._vault.get_key(row[0])

    def has_provider(self, provider: str) -> bool:
        return self.get_active_key(provider) is not None
