from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from typing import Any

import bcrypt
import pymysql
import pymysql.cursors
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

_admin = APIRouter(prefix="/admin/api")
_SECRET = os.getenv("CECHE_ADMIN_SECRET", secrets.token_hex(32))


def _db() -> pymysql.Connection:
    """Get MySQL connection using env vars or defaults."""
    return pymysql.connect(
        host=os.getenv("CECHE_MYSQL_HOST", "localhost"),
        port=int(os.getenv("CECHE_MYSQL_PORT", "3306")),
        user=os.getenv("CECHE_MYSQL_USER", "ceche"),
        password=os.getenv("CECHE_MYSQL_PASSWORD", ""),
        database=os.getenv("CECHE_MYSQL_DATABASE", "ceche"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _init_db() -> None:
    """Ensure all admin tables exist in MySQL."""
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(100) DEFAULT '',
                    role ENUM('admin','editor') DEFAULT 'editor',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS blog_posts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    slug VARCHAR(255) UNIQUE NOT NULL,
                    content LONGTEXT NOT NULL,
                    excerpt TEXT DEFAULT NULL,
                    featured_image VARCHAR(500) DEFAULT NULL,
                    status ENUM('draft','published') DEFAULT 'draft',
                    published_at TIMESTAMP NULL DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documentation_pages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    slug VARCHAR(255) UNIQUE NOT NULL,
                    content LONGTEXT NOT NULL,
                    category VARCHAR(100) DEFAULT '',
                    sort_order INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key_name VARCHAR(100) PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '',
                    description VARCHAR(500) DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    key_hash VARCHAR(255) NOT NULL,
                    tier ENUM('free','pro','enterprise') DEFAULT 'free',
                    rate_limit INT DEFAULT 60,
                    active TINYINT(1) DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP NULL DEFAULT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tier VARCHAR(50) UNIQUE NOT NULL,
                    requests_per_minute INT DEFAULT 60,
                    burst_size INT DEFAULT 10,
                    concurrent_limit INT DEFAULT 5,
                    enabled TINYINT(1) DEFAULT 1
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            # Seed default rate limits if empty
            cur.execute("SELECT COUNT(*) as c FROM rate_limits")
            if cur.fetchone()["c"] == 0:
                for t in ["free", "pro", "enterprise"]:
                    cur.execute(
                        "INSERT INTO rate_limits (tier, requests_per_minute, burst_size, concurrent_limit) VALUES (%s,%s,%s,%s)",
                        (t, 60, 10, 5) if t == "free" else (300, 30, 20) if t == "pro" else (1000, 100, 50),
                    )
    finally:
        conn.close()


def _token_make(user_id: int, role: str) -> str:
    payload = f"{user_id}:{role}:{int(time.time()) + 86400}"
    sig = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}:{sig}"


def _token_verify(token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(":")
        if len(parts) != 4:
            return None
        user_id, role, exp_str, sig = parts
        exp = int(exp_str)
        if exp < time.time():
            return None
        expected = hmac.new(
            _SECRET.encode(), f"{user_id}:{role}:{exp_str}".encode(), hashlib.sha256,
        ).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return None
        return {"user_id": int(user_id), "role": role, "exp": exp}
    except (ValueError, IndexError):
        return None


def _get_token(request: Request) -> dict[str, Any] | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return _token_verify(auth[7:])
    cookie = request.cookies.get("ceche_admin_token")
    if cookie:
        return _token_verify(cookie)
    return None


def _require_admin(request: Request) -> dict[str, Any]:
    token = _get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token


def _row_to_dict(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}
    for k, v in row.items():
        if isinstance(v, bytes):
            row[k] = v.decode()
    return row


# --- Auth ---

class LoginRequest(BaseModel):
    email: str
    password: str


@_admin.post("/login")
async def admin_login(req: LoginRequest, response: Response) -> dict[str, Any]:
    _ensure_init()
    email = req.email.strip().lower()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash, role FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if row is None:
            pw = os.getenv("CECHE_ADMIN_PASSWORD")
            if not pw or req.password != pw:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
            cur.execute("INSERT INTO users (email, password_hash, name, role) VALUES (%s,%s,%s,%s)",
                        (email, hashed, "Admin", "admin"))
            user_id = cur.lastrowid
            token = _token_make(user_id, "admin")
            response.set_cookie(key="ceche_admin_token", value=token, httponly=True, max_age=86400, samesite="lax")
            return {"token": token, "role": "admin", "first_run": True}
        if not bcrypt.checkpw(req.password.encode(), row["password_hash"].encode()):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = _token_make(row["id"], row["role"])
        response.set_cookie(key="ceche_admin_token", value=token, httponly=True, max_age=86400, samesite="lax")
        return {"token": token, "role": row["role"]}
    finally:
        conn.close()


@_admin.post("/logout")
async def admin_logout(response: Response) -> dict[str, Any]:
    response.delete_cookie("ceche_admin_token")
    return {"ok": True}


@_admin.get("/verify")
async def admin_verify(request: Request) -> dict[str, Any]:
    t = _require_admin(request)
    return {"ok": True, "role": t["role"]}


# --- Stats ---

@_admin.get("/stats")
async def admin_stats(request: Request) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM appraisals")
        total = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) as c FROM appraisals WHERE created_at > UNIX_TIMESTAMP() - 86400")
        today = cur.fetchone()["c"]
        cur.execute("SELECT AVG(estimated_value) as v FROM appraisals WHERE estimated_value IS NOT NULL")
        avg = cur.fetchone()["v"]
        cur.execute("SELECT domain, estimated_value FROM appraisals WHERE estimated_value IS NOT NULL ORDER BY estimated_value DESC LIMIT 1")
        top = cur.fetchone()
        return {"total_appraisals": total, "today_appraisals": today, "avg_value": round(avg, 2) if avg else None, "top_domain": top["domain"] if top else None}
    finally:
        conn.close()


@_admin.get("/recent")
async def admin_recent(request: Request, limit: int = 10) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT domain, estimated_value, confidence, source, created_at FROM appraisals ORDER BY created_at DESC LIMIT %s", (limit,))
        return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# --- Settings ---

@_admin.get("/settings")
async def admin_settings_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM settings ORDER BY key_name")
        return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.put("/settings/{key_name}")
async def admin_settings_update(request: Request, key_name: str) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO settings (key_name, value, description) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE value=%s, description=%s",
                    (key_name, body.get("value", ""), body.get("description", ""), body.get("value", ""), body.get("description", "")))
        return {"ok": True}
    finally:
        conn.close()


@_admin.delete("/settings/{key_name}")
async def admin_settings_delete(request: Request, key_name: str) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM settings WHERE key_name = %s", (key_name,))
        return {"ok": True}
    finally:
        conn.close()


# --- Blog ---

@_admin.get("/blog")
async def admin_blog_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, title, slug, excerpt, status, UNIX_TIMESTAMP(published_at) as published_at, UNIX_TIMESTAMP(created_at) as created_at, UNIX_TIMESTAMP(updated_at) as updated_at FROM blog_posts ORDER BY created_at DESC")
        return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.post("/blog")
async def admin_blog_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    slug = body.get("slug", body.get("title", "untitled").lower().replace(" ", "-").replace("/", "-")[:100])
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO blog_posts (title, slug, content, excerpt, featured_image, status) VALUES (%s,%s,%s,%s,%s,%s)",
                    (body.get("title", ""), slug, body.get("content", ""), body.get("excerpt", ""), body.get("featured_image", ""), body.get("status", "draft")))
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


@_admin.get("/blog/{post_id}")
async def admin_blog_get(request: Request, post_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM blog_posts WHERE id = %s", (post_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else {}
    finally:
        conn.close()


@_admin.put("/blog/{post_id}")
async def admin_blog_update(request: Request, post_id: int) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE blog_posts SET title=%s, slug=%s, content=%s, excerpt=%s, featured_image=%s, status=%s WHERE id=%s",
                    (body.get("title", ""), body.get("slug", ""), body.get("content", ""), body.get("excerpt", ""), body.get("featured_image", ""), body.get("status", "draft"), post_id))
        if body.get("status") == "published":
            cur.execute("UPDATE blog_posts SET published_at = NOW() WHERE id = %s AND published_at IS NULL", (post_id,))
        return {"ok": True}
    finally:
        conn.close()


@_admin.delete("/blog/{post_id}")
async def admin_blog_delete(request: Request, post_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM blog_posts WHERE id = %s", (post_id,))
        return {"ok": True}
    finally:
        conn.close()


# --- Documentation ---

@_admin.get("/docs")
async def admin_docs_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM documentation_pages ORDER BY sort_order, title")
        return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.post("/docs")
async def admin_docs_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    slug = body.get("slug", body.get("title", "untitled").lower().replace(" ", "-")[:100])
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO documentation_pages (title, slug, content, category, sort_order) VALUES (%s,%s,%s,%s,%s)",
                    (body.get("title", ""), slug, body.get("content", ""), body.get("category", ""), body.get("sort_order", 0)))
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


@_admin.get("/docs/{doc_id}")
async def admin_docs_get(request: Request, doc_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM documentation_pages WHERE id = %s", (doc_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else {}
    finally:
        conn.close()


@_admin.put("/docs/{doc_id}")
async def admin_docs_update(request: Request, doc_id: int) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE documentation_pages SET title=%s, slug=%s, content=%s, category=%s, sort_order=%s WHERE id=%s",
                    (body.get("title", ""), body.get("slug", ""), body.get("content", ""), body.get("category", ""), body.get("sort_order", 0), doc_id))
        return {"ok": True}
    finally:
        conn.close()


@_admin.delete("/docs/{doc_id}")
async def admin_docs_delete(request: Request, doc_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM documentation_pages WHERE id = %s", (doc_id,))
        return {"ok": True}
    finally:
        conn.close()


# --- API Keys ---

@_admin.get("/api-keys")
async def admin_api_keys_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, tier, rate_limit, active, UNIX_TIMESTAMP(created_at) as created_at FROM api_keys ORDER BY created_at DESC")
        return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.post("/api-keys")
async def admin_api_keys_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    raw_key = "ceche_" + uuid.uuid4().hex[:24]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO api_keys (name, key_hash, tier, rate_limit) VALUES (%s,%s,%s,%s)",
                    (body.get("name", "Unnamed"), key_hash, body.get("tier", "free"), body.get("rate_limit", 60)))
        return {"ok": True, "key": raw_key}
    finally:
        conn.close()


@_admin.delete("/api-keys/{key_id}")
async def admin_api_keys_delete(request: Request, key_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM api_keys WHERE id = %s", (key_id,))
        return {"ok": True}
    finally:
        conn.close()


# --- Rate Limits ---

@_admin.get("/rate-limits")
async def admin_rate_limits_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM rate_limits ORDER BY tier")
        return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.put("/rate-limits/{tier}")
async def admin_rate_limits_update(request: Request, tier: str) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO rate_limits (tier, requests_per_minute, burst_size, concurrent_limit, enabled) VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE requests_per_minute=%s, burst_size=%s, concurrent_limit=%s, enabled=%s",
                    (tier, body.get("requests_per_minute", 60), body.get("burst_size", 10), body.get("concurrent_limit", 5), body.get("enabled", 1),
                     body.get("requests_per_minute", 60), body.get("burst_size", 10), body.get("concurrent_limit", 5), body.get("enabled", 1)))
        return {"ok": True}
    finally:
        conn.close()


# --- Users ---

@_admin.get("/users")
async def admin_users_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, email, name, role, UNIX_TIMESTAMP(created_at) as created_at FROM users ORDER BY created_at ASC")
        return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.post("/users")
async def admin_users_invite(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    hashed = bcrypt.hashpw(body.get("password", secrets.token_hex(8)).encode(), bcrypt.gensalt()).decode()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO users (email, password_hash, name, role) VALUES (%s,%s,%s,%s)",
                    (body.get("email", ""), hashed, body.get("name", ""), body.get("role", "editor")))
        return {"ok": True, "id": cur.lastrowid}
    except pymysql.err.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already exists") from None
    finally:
        conn.close()


@_admin.delete("/users/{user_id}")
async def admin_users_delete(request: Request, user_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        return {"ok": True}
    finally:
        conn.close()


# --- Domains ---

@_admin.get("/domains")
async def admin_domains_list(request: Request, page: int = 1, per_page: int = 50, search: str = "", tld: str = "", source: str = "") -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        where = []
        params: list[Any] = []
        if search:
            where.append("domain LIKE %s")
            params.append(f"%{search}%")
        if tld:
            where.append("domain LIKE %s")
            params.append(f"%.{tld}")
        if source:
            where.append("source = %s")
            params.append(source)
        w = (" WHERE " + " AND ".join(where)) if where else ""
        cur.execute(f"SELECT COUNT(*) as c FROM appraisals{w}", params)
        total = cur.fetchone()["c"]
        offset = (page - 1) * per_page
        cur.execute(f"SELECT id, domain, estimated_value, confidence, tld_score, weight_profile, source, UNIX_TIMESTAMP(created_at) as created_at FROM appraisals{w} ORDER BY created_at DESC LIMIT %s OFFSET %s", params + [per_page, offset])
        return {"domains": [_row_to_dict(r) for r in cur.fetchall()], "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@_admin.get("/domains/{domain_id}")
async def admin_domain_detail(request: Request, domain_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM appraisals WHERE id = %s", (domain_id,))
        row = cur.fetchone()
        if not row:
            return {}
        d = _row_to_dict(row)
        if d.get("modules_json"):
            d["modules"] = json.loads(d["modules_json"])
        return d
    finally:
        conn.close()


# Initialize tables on first request (not at import time to avoid blocking)
_initialized = False


def _ensure_init() -> None:
    global _initialized
    if not _initialized:
        try:
            _init_db()
            _initialized = True
        except Exception:
            pass  # MySQL might not be available — endpoints will handle this
