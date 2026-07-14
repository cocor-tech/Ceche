# Layer 1 — Secure Credential Vault

## Overview

The credential vault manages all AI provider API keys with enterprise-grade security. It supports three input channels: environment variables, direct user input, and agent-to-agent JWT exchange. Keys are encrypted at rest, access is audited, and temporary grants prevent long-lived key exposure.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CredentialVault                             │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Encryption   │  │ Grant Manager│  │ Audit Logger         │   │
│  │ (Fernet AES) │  │ (JWT + TTL)  │  │ (structured JSON)    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                      │              │
│  ┌──────┴─────────────────┴──────────────────────┴──────────┐   │
│  │                   Encrypted Store (SQLite)                │   │
│  │  keys(id, provider, encrypted_value, created_by, grants)  │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Input Channels:                                                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐     │
│  │ CECHE_*_KEY│  │ CLI --ai-  │  │ Agent JWT              │     │
│  │ env vars   │  │ key flag   │  │ (signed token)         │     │
│  └────────────┘  └────────────┘  └────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## Data Model

### Encrypted Key Store

```sql
CREATE TABLE IF NOT EXISTS keys (
    id            TEXT PRIMARY KEY,    -- UUID
    provider      TEXT NOT NULL,         -- "openai", "anthropic", "ollama"
    label         TEXT NOT NULL,         -- user-friendly name
    encrypted_key TEXT NOT NULL,         -- Fernet-encrypted API key
    created_at    INTEGER NOT NULL,      -- Unix timestamp
    created_by    TEXT NOT NULL,         -- agent_id, user_id, or "env"
    revoked       INTEGER DEFAULT 0      -- 0 = active, 1 = revoked
);

CREATE TABLE IF NOT EXISTS grants (
    id            TEXT PRIMARY KEY,      -- UUID
    key_id        TEXT NOT NULL,         -- FK to keys.id
    grantor       TEXT NOT NULL,         -- who issued the grant
    grantee       TEXT NOT NULL,         -- who received the grant
    ttl_seconds   INTEGER NOT NULL,      -- grant lifetime
    created_at    INTEGER NOT NULL,      -- Unix timestamp
    expires_at    INTEGER NOT NULL,      -- created_at + ttl_seconds
    jwt_hash      TEXT NOT NULL,         -- SHA-256 of the JWT
    used_at       INTEGER,              -- when first accessed (NULL = unused)
    revoked       INTEGER DEFAULT 0      -- 0 = active, 1 = revoked
);

CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     INTEGER NOT NULL,      -- Unix timestamp
    action        TEXT NOT NULL,         -- "grant_create", "grant_use", "key_store", "key_revoke", "access_denied"
    actor         TEXT NOT NULL,         -- agent_id, user_id, or "system"
    target        TEXT NOT NULL,         -- grant_id or key_id
    detail        TEXT NOT NULL,         -- JSON: {ip, provider, ttl, ...}
    success       INTEGER NOT NULL       -- 0 or 1
);

CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_grants_expires ON grants(expires_at);
```

## Encryption

- **Algorithm:** Fernet (AES-128-CBC with HMAC-SHA256 authentication)
- **Key derivation:** PBKDF2 from a master passphrase or auto-generated seed
- **Master key storage:** in `CECHE_VAULT_KEY` environment variable, or `~/.config/ceche/vault.key`
- **Rotation:** `vault rotate` generates new Fernet key, re-encrypts all stored keys
- **In-memory:** decrypted keys are held in a `_cache` dict with a 5-minute TTL, never logged

## Agent-to-Agent Protocol (JWT Exchange)

### JWT Payload

```json
{
  "sub": "agent-id",           // e.g., "sqlx-session-abc123"
  "iat": 1783966566,           // issued at
  "exp": 1784052966,           // expires (24h default)
  "provider": "openai",        // "openai" | "anthropic" | "ollama"
  "key_sha256": "abc123...",   // first 16 chars of SHA-256(key)
  "ttl_hours": 24,             // requested grant duration
  "grantor": "codex-v2",       // which agent issued this
  "permissions": ["appraise"]  // what this key can be used for
}
```

### Flow

1. **External agent** (me, Claude, any AI) generates the JWT using a shared signing secret
2. **Ceche receives** the JWT via `--ai-jwt` flag or `CECHE_AI_JWT` env var
3. **Vault verifies** the JWT signature using the stored agent public key
4. **Key is extracted**, encrypted with Fernet, stored in the `keys` table
5. **A grant** is created linking the key to the agent with the requested TTL
6. **Grant ID** is returned to the adapter for runtime use
7. **At runtime**, adapters call `vault.get_key(grant_id)` → vault checks TTL, decrypts, returns key
8. **Expired grants** are silently rejected; the adapter falls back to NoOp

### CLI Commands

```bash
# Agent passes a JWT directly
ceche appraise example.com --ai-jwt "eyJhbGciOi..."

# User stores a key manually
ceche ai key add --provider openai --key "sk-..." --label "prod"

# User creates a grant for a specific agent
ceche ai grant create --agent-id "codex-v2" --ttl 24h --label "dev-session"

# List active grants
ceche ai grant list

# Revoke a grant
ceche ai grant revoke --grant-id "grant_abc123"

# View audit log
ceche ai audit --limit 50 --actor "codex-v2"
```

## Audit Trail

Every operation is logged:

```
2026-07-14T12:00:00Z  action=key_store    actor=env          provider=openai   success=1
2026-07-14T12:00:01Z  action=grant_create actor=codex-v2    grantee=sqlx-123  ttl=86400  success=1
2026-07-14T12:00:05Z  action=grant_use    actor=sqlx-123    detail={"module":"m6"}  success=1
2026-07-14T12:30:00Z  action=access_denied actor=unknown   detail={"reason":"signature_mismatch"}  success=0
```

Audit logs are structured JSON, queryable by actor, action, time range. They never contain plaintext keys (only key SHA-256 prefixes or grant IDs).

## Security Properties

| Property | Implementation |
|---|---|
| Encryption at rest | Fernet AES-128-CBC, key not stored alongside data |
| No plaintext in logs | Only SHA-256 prefix, grant IDs, never full keys |
| Time-bound access | Grants expire automatically, no permanent key exposure |
| Agent identity | JWT signatures verify the issuing agent |
| Revocation | Keys and grants can be revoked individually |
| Audit trail | Every key access, grant creation, and denial is logged |
| Privilege separation | Adapters never see raw keys — they get a grant ID and vault handles decryption |

## Implementation Files

```
ceche/infrastructure/ai/
├── security/
│   ├── __init__.py
│   ├── vault.py           # CredentialVault class — encrypt, store, retrieve, revoke
│   ├── encryption.py      # Fernet wrapper with key rotation
│   ├── grants.py          # GrantManager — JWT verification, TTL enforcement
│   ├── audit.py           # AuditLogger — structured logging to SQLite
│   ├── jwt_agent.py       # AgentJWT — sign, verify, extract payload
│   └── schema.sql         # SQLite schema (keys, grants, audit_log)
```

## Dependencies

- `cryptography` (Fernet)
- `PyJWT` (JWT signing/verification)
- `sqlite3` (built into Python)
- No external key management service required

## Best Practices

### Key Storage
- Never store the vault master key in the same filesystem as the encrypted data. Use a separate secret manager (Vault, AWS Secrets Manager, or env-only on ephemeral containers).
- Rotate the Fernet key every 90 days. Automate with a cron job or CI pipeline.
- Store the vault SQLite file in a directory with restricted permissions (chmod 600 on the file, chmod 700 on the directory).

### Agent-to-Agent JWT Exchange
- Sign JWTs with RS256 (asymmetric) not HS256 (symmetric). This means the signing agent holds a private key and Ceche holds only the public key — the signing key is never shared.
- Include a `jti` (JWT ID) claim in every JWT to prevent replay attacks. Track used JTIs in the grants table for 7 days.
- Set TTL conservatively — default 1 hour, max 24 hours. Longer grants should require explicit approval.
- Never log the raw JWT. Log only the JWT hash (SHA-256) and the decoded claims (without the key material).

### Audit Log
- Ship audit logs to a centralized system (ELK, Datadog, Splunk) within 1 minute of writing. Use a background thread that tails the SQLite WAL.
- Implement log rotation: archive audit records older than 90 days to cold storage, delete after 1 year.
- Set up alerts for: 3+ consecutive access_denied events within 5 minutes, any grant_use with revoked=true, any key_store from an unrecognized agent_id.

## Common Mistakes & How to Avoid Them

| Mistake | Why It Happens | Prevention |
|---|---|---|
| **Committing the vault key to git** | Developer adds .env to repo or hardcodes key in config | Add `CECHE_VAULT_KEY` to `.gitignore`, use pre-commit hook to scan for hex strings > 32 chars |
| **Using the same Fernet key across environments** | Copying the vault.db between dev/staging/prod | Generate a unique master key per environment. Use `CECHE_VAULT_KEY` env var, never persist it. |
| **Grant TTL too long** | Setting TTL to 365 days "for convenience" | Enforce max TTL of 24 hours in the GrantManager. Longer access requires a new grant. |
| **JWT signed with HS256 and a weak secret** | Using "secret" or "password" as the signing key | Require RS256 minimum. Validate key length (≥ 2048 bits for RSA) at grant creation time. |
| **Not revoking grants when an agent session ends** | Agent disconnects without cleanup | Grants auto-expire via TTL. Additionally, implement a `/ai/revoke-session` endpoint that the agent calls on disconnect. |
| **Audit table growing unbounded** | No cleanup policy | Add a daily cron that deletes audit records older than the retention period. |

## Enterprise-Grade Implementation Checklist

- [ ] Fernet encryption with PBKDF2 key derivation (≥ 600,000 iterations)
- [ ] RS256 JWT signing (RSA 2048-bit minimum)
- [ ] JWT jti claim for replay protection
- [ ] All database files chmod 600, parent directory chmod 700
- [ ] Audit logs shipped to centralized system within 60 seconds
- [ ] Alert on: 3+ denied accesses in 5 min, revoked grant usage, unknown agent_id
- [ ] Max grant TTL enforced at 24 hours
- [ ] Grant auto-revocation on agent disconnect
- [ ] Daily audit log rotation and archival
- [ ] Pre-commit hook scanning for hardcoded secrets
- [ ] Master key never stored on same filesystem as encrypted data
- [ ] Quarterly Fernet key rotation
- [ ] Integration test: JWT replay attack is rejected
- [ ] Integration test: expired grant returns 401
- [ ] Integration test: revoked key cannot be used
