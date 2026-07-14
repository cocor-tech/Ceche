"""Tests for Layer 1 — Secure Credential Vault."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ceche.infrastructure.ai.security.audit import AuditLogger
from ceche.infrastructure.ai.security.encryption import EncryptionManager, generate_fernet_key
from ceche.infrastructure.ai.security.grants import GrantManager
from ceche.infrastructure.ai.security.vault import CredentialVault


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        em = EncryptionManager()
        plain = "sk-test-key-12345"
        encrypted = em.encrypt(plain)
        decrypted = em.decrypt(encrypted)
        assert decrypted == plain

    def test_encrypt_produces_different_ciphertext(self):
        em = EncryptionManager()
        c1 = em.encrypt("hello")
        c2 = em.encrypt("hello")
        assert c1 != c2

    def test_from_passphrase(self):
        em = EncryptionManager.from_passphrase("my-secret-passphrase")
        encrypted = em.encrypt("data")
        assert em.decrypt(encrypted) == "data"

    def test_generate_fernet_key(self):
        key = generate_fernet_key()
        assert len(key) == 44
        assert key.endswith("=")


class TestAuditLogger:
    def test_log_and_query(self):
        db = str(Path(tempfile.mkdtemp()) / "audit.db")
        logger = AuditLogger(db)
        logger.log("key_store", "agent-123", "key-abc", {"provider": "openai"})
        results = logger.query(actor="agent-123")
        assert len(results) == 1
        assert results[0]["action"] == "key_store"

    def test_query_by_action(self):
        db = str(Path(tempfile.mkdtemp()) / "audit.db")
        logger = AuditLogger(db)
        logger.log("grant_create", "admin", "g1")
        logger.log("key_store", "admin", "k1")
        results = logger.query(action="key_store")
        assert len(results) == 1
        assert results[0]["action"] == "key_store"


class TestGrantManager:
    def test_create_and_validate(self):
        db = str(Path(tempfile.mkdtemp()) / "grants.db")
        gm = GrantManager(db)
        gid = gm.create("key-1", "admin", "agent-1", 3600, "hash123")
        assert gm.is_valid(gid) is True

    def test_expired_grant(self):
        db = str(Path(tempfile.mkdtemp()) / "grants.db")
        gm = GrantManager(db)
        gid = gm.create("key-1", "admin", "agent-1", -1, "hash123")
        assert gm.is_valid(gid) is False

    def test_revoke(self):
        db = str(Path(tempfile.mkdtemp()) / "grants.db")
        gm = GrantManager(db)
        gid = gm.create("key-1", "admin", "agent-1", 3600, "hash123")
        assert gm.revoke(gid) is True
        assert gm.is_valid(gid) is False

    def test_mark_used(self):
        db = str(Path(tempfile.mkdtemp()) / "grants.db")
        gm = GrantManager(db)
        gid = gm.create("key-1", "admin", "agent-1", 3600, "hash123")
        gm.mark_used(gid)
        results = gm.list_active(grantee="agent-1")
        assert len(results) == 1
        assert results[0]["used_at"] is not None

    def test_list_active(self):
        db = str(Path(tempfile.mkdtemp()) / "grants.db")
        gm = GrantManager(db)
        gm.create("key-1", "admin", "agent-1", 3600, "hash1")
        gm.create("key-2", "admin", "agent-2", 3600, "hash2")
        results = gm.list_active(grantee="agent-1")
        assert len(results) == 1
        assert results[0]["grantee"] == "agent-1"


class TestCredentialVault:
    def test_store_and_retrieve_key(self):
        db = str(Path(tempfile.mkdtemp()) / "vault.db")
        vault = CredentialVault(db_path=db)
        key_id = vault.store_key("sk-test-abc123", "openai", "test-key")
        retrieved = vault.get_key(key_id)
        assert retrieved == "sk-test-abc123"

    def test_revoked_key_returns_none(self):
        db = str(Path(tempfile.mkdtemp()) / "vault.db")
        vault = CredentialVault(db_path=db)
        key_id = vault.store_key("sk-test-xyz", "openai")
        vault.revoke_key(key_id)
        assert vault.get_key(key_id) is None

    def test_unknown_key_returns_none(self):
        db = str(Path(tempfile.mkdtemp()) / "vault.db")
        vault = CredentialVault(db_path=db)
        assert vault.get_key("nonexistent") is None

    def test_audit_log_entries(self):
        db = str(Path(tempfile.mkdtemp()) / "vault.db")
        vault = CredentialVault(db_path=db)
        vault.store_key("sk-test", "openai", "audit-test")
        logs = vault.audit_log(action="key_store")
        assert len(logs) >= 1
        assert logs[0]["action"] == "key_store"

    def test_multiple_keys(self):
        db = str(Path(tempfile.mkdtemp()) / "vault.db")
        vault = CredentialVault(db_path=db)
        k1 = vault.store_key("key-a", "openai")
        k2 = vault.store_key("key-b", "anthropic")
        assert vault.get_key(k1) == "key-a"
        assert vault.get_key(k2) == "key-b"

    def test_persistence_across_instances(self):
        db = str(Path(tempfile.mkdtemp()) / "vault.db")
        em = EncryptionManager()
        vault1 = CredentialVault(db_path=db, encryption=em)
        key_id = vault1.store_key("persist-test-key", "openai")
        vault2 = CredentialVault(db_path=db, encryption=em)
        assert vault2.get_key(key_id) == "persist-test-key"

    def test_grant_revoke(self):
        db = str(Path(tempfile.mkdtemp()) / "vault.db")
        vault = CredentialVault(db_path=db)
        gid = vault._grants.create("key-x", "admin", "agent-1", 3600, "hash")
        assert vault.revoke_grant(gid) is True

    def test_list_grants(self):
        db = str(Path(tempfile.mkdtemp()) / "vault.db")
        vault = CredentialVault(db_path=db)
        gid = vault._grants.create("key-y", "admin", "agent-99", 3600, "hash")
        grants = vault.list_grants(grantee="agent-99")
        assert len(grants) >= 1
        assert any(g["id"] == gid for g in grants)
