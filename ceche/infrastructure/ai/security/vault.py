from __future__ import annotations

import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from ceche.infrastructure.ai.security.audit import AuditLogger
from ceche.infrastructure.ai.security.encryption import EncryptionManager
from ceche.infrastructure.ai.security.grants import GrantManager
from ceche.infrastructure.ai.security.jwt_agent import AgentJWT


class CredentialVault:
    def __init__(
        self,
        db_path: str | None = None,
        public_key_pem: str | None = None,
        encryption: EncryptionManager | None = None,
    ) -> None:
        default = Path.home() / ".config" / "ceche" / "vault.db"
        self._db_path = db_path or str(default)
        self._encryption = encryption or self._init_encryption()
        self._jwt = AgentJWT(public_key_pem=public_key_pem)
        self._grants = GrantManager(self._db_path)
        self._audit = AuditLogger(self._db_path)
        self._init()

    def _init_encryption(self) -> EncryptionManager:
        vault_key = os.getenv("CECHE_VAULT_KEY")
        if vault_key:
            return EncryptionManager(master_key=vault_key)
        key_path = Path.home() / ".config" / "ceche" / "vault.key"
        if key_path.exists():
            return EncryptionManager(master_key=key_path.read_text().strip())
        return EncryptionManager()

    def _init(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id            TEXT PRIMARY KEY,
                provider      TEXT NOT NULL,
                label         TEXT NOT NULL,
                encrypted_key TEXT NOT NULL,
                created_at    INTEGER NOT NULL,
                created_by    TEXT NOT NULL,
                revoked       INTEGER DEFAULT 0,
                expires_at    INTEGER
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_keys_provider ON keys(provider)"
        )
        conn.commit()
        conn.close()

    def store_key(
        self, key: str, provider: str, label: str = "", created_by: str = "user",
        expires_at: int | None = None,
    ) -> str:
        key_id = str(uuid.uuid4())
        encrypted = self._encryption.encrypt(key)
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO keys "
            "(id, provider, label, encrypted_key, created_at, created_by, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key_id, provider, label, encrypted, int(time.time()), created_by, expires_at),
        )
        conn.commit()
        conn.close()
        self._audit.log("key_store", created_by, key_id, {"provider": provider})
        return key_id

    def get_key(self, key_id: str) -> str | None:
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT encrypted_key, revoked FROM keys WHERE id = ?",
            (key_id,),
        ).fetchone()
        conn.close()
        if row is None or row[1]:
            self._audit.log(
                "access_denied", "system", key_id,
                {"reason": "revoked_or_missing"}, success=False,
            )
            return None
        try:
            plain = self._encryption.decrypt(row[0])
            self._audit.log("key_access", "system", key_id)
            return plain
        except Exception:
            self._audit.log(
                "access_denied", "system", key_id,
                {"reason": "decrypt_failed"}, success=False,
            )
            return None

    def revoke_key(self, key_id: str) -> bool:
        conn = sqlite3.connect(self._db_path)
        cursor = conn.execute(
            "UPDATE keys SET revoked = 1 WHERE id = ?", (key_id,)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected:
            self._audit.log("key_revoke", "system", key_id)
        return affected > 0

    def accept_agent_jwt(
        self, token: str, api_key: str, provider: str
    ) -> str | None:
        claims = AgentJWT.extract_claims_unsigned(token)
        if claims is None:
            self._audit.log(
                "access_denied", "unknown", "jwt",
                {"reason": "invalid_jwt"}, success=False,
            )
            return None
        if claims.exp < int(time.time()):
            self._audit.log(
                "access_denied", claims.sub, "jwt",
                {"reason": "expired"}, success=False,
            )
            return None
        key_id = self.store_key(
            api_key, provider, f"agent-{claims.sub}", created_by=claims.sub,
        )
        jwt_hash = GrantManager.hash_jwt(token)
        grant_id = self._grants.create(
            key_id=key_id,
            grantor=claims.grantor,
            grantee=claims.sub,
            ttl_seconds=claims.ttl_hours * 3600,
            jwt_hash=jwt_hash,
        )
        detail = {
            "grantee": claims.sub,
            "provider": provider,
            "ttl_hours": claims.ttl_hours,
        }
        self._audit.log("grant_create", claims.grantor, grant_id, detail)
        return grant_id

    def get_key_by_grant(self, grant_id: str) -> str | None:
        if not self._grants.is_valid(grant_id):
            self._audit.log(
                "access_denied", "system", grant_id,
                {"reason": "grant_invalid"}, success=False,
            )
            return None
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT key_id FROM grants WHERE id = ?", (grant_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        key = self.get_key(row[0])
        if key:
            self._grants.mark_used(grant_id)
            self._audit.log("grant_use", "system", grant_id)
        return key

    def audit_log(
        self,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self._audit.query(actor=actor, action=action, limit=limit)

    def revoke_grant(self, grant_id: str) -> bool:
        return self._grants.revoke(grant_id)

    def list_grants(self, grantee: str | None = None) -> list[dict[str, Any]]:
        return self._grants.list_active(grantee=grantee)
