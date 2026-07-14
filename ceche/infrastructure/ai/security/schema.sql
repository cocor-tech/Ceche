-- Ceche AI Credential Vault Schema
-- Enterprise-grade encrypted credential storage

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS keys (
    id            TEXT PRIMARY KEY,
    provider      TEXT NOT NULL,
    label         TEXT NOT NULL,
    encrypted_key TEXT NOT NULL,
    created_at    INTEGER NOT NULL,
    created_by    TEXT NOT NULL,
    revoked       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS grants (
    id            TEXT PRIMARY KEY,
    key_id        TEXT NOT NULL REFERENCES keys(id),
    grantor       TEXT NOT NULL,
    grantee       TEXT NOT NULL,
    ttl_seconds   INTEGER NOT NULL,
    created_at    INTEGER NOT NULL,
    expires_at    INTEGER NOT NULL,
    jwt_hash      TEXT NOT NULL,
    used_at       INTEGER,
    revoked       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     INTEGER NOT NULL,
    action        TEXT NOT NULL,
    actor         TEXT NOT NULL,
    target        TEXT NOT NULL,
    detail        TEXT NOT NULL,
    success       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_keys_provider ON keys(provider);
CREATE INDEX IF NOT EXISTS idx_grants_expires ON grants(expires_at);
CREATE INDEX IF NOT EXISTS idx_grants_grantee ON grants(grantee);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
