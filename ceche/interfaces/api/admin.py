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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS faq_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    sort_order INT DEFAULT 0,
                    active TINYINT(1) DEFAULT 1
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pricing_tiers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    price_label VARCHAR(50) NOT NULL,
                    price_subtext VARCHAR(100) DEFAULT '',
                    features JSON NOT NULL,
                    cta_label VARCHAR(50) DEFAULT 'Get Started',
                    cta_url VARCHAR(255) DEFAULT '',
                    highlighted TINYINT(1) DEFAULT 0,
                    sort_order INT DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS enterprise_features (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT NOT NULL,
                    sort_order INT DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS comparisons (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    competitor VARCHAR(100) NOT NULL,
                    slug VARCHAR(100) UNIQUE NOT NULL,
                    rows_data JSON NOT NULL,
                    meta_title VARCHAR(255) DEFAULT '',
                    meta_description TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    slug VARCHAR(100) UNIQUE NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    meta_title VARCHAR(255) DEFAULT '',
                    meta_description TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
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


# --- FAQ ---

@_admin.get("/faq")
async def admin_faq_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM faq_items ORDER BY sort_order")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.post("/faq")
async def admin_faq_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO faq_items (question, answer, sort_order, active) VALUES (%s,%s,%s,%s)",
                    (body.get("question", ""), body.get("answer", ""), body.get("sort_order", 0), body.get("active", 1)))
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


@_admin.put("/faq/{item_id}")
async def admin_faq_update(request: Request, item_id: int) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE faq_items SET question=%s, answer=%s, sort_order=%s, active=%s WHERE id=%s",
                    (body.get("question", ""), body.get("answer", ""), body.get("sort_order", 0), body.get("active", 1), item_id))
        return {"ok": True}
    finally:
        conn.close()


@_admin.delete("/faq/{item_id}")
async def admin_faq_delete(request: Request, item_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM faq_items WHERE id = %s", (item_id,))
        return {"ok": True}
    finally:
        conn.close()


# --- Pricing ---

@_admin.get("/pricing")
async def admin_pricing_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM pricing_tiers ORDER BY sort_order")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.post("/pricing")
async def admin_pricing_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO pricing_tiers (name, price_label, price_subtext, features, cta_label, cta_url, highlighted, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (body.get("name", ""), body.get("price_label", ""), body.get("price_subtext", ""),
                     json.dumps(body.get("features", [])), body.get("cta_label", "Get Started"),
                     body.get("cta_url", ""), body.get("highlighted", 0), body.get("sort_order", 0)))
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


@_admin.put("/pricing/{tier_id}")
async def admin_pricing_update(request: Request, tier_id: int) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE pricing_tiers SET name=%s, price_label=%s, price_subtext=%s, features=%s, cta_label=%s, cta_url=%s, highlighted=%s, sort_order=%s WHERE id=%s",
                    (body.get("name", ""), body.get("price_label", ""), body.get("price_subtext", ""),
                     json.dumps(body.get("features", [])), body.get("cta_label", "Get Started"),
                     body.get("cta_url", ""), body.get("highlighted", 0), body.get("sort_order", 0), tier_id))
        return {"ok": True}
    finally:
        conn.close()


@_admin.delete("/pricing/{tier_id}")
async def admin_pricing_delete(request: Request, tier_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM pricing_tiers WHERE id = %s", (tier_id,))
        return {"ok": True}
    finally:
        conn.close()


# --- Enterprise Features ---

@_admin.get("/features")
async def admin_features_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM enterprise_features ORDER BY sort_order")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.post("/features")
async def admin_features_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO enterprise_features (title, description, sort_order) VALUES (%s,%s,%s)",
                    (body.get("title", ""), body.get("description", ""), body.get("sort_order", 0)))
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


@_admin.put("/features/{feature_id}")
async def admin_features_update(request: Request, feature_id: int) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE enterprise_features SET title=%s, description=%s, sort_order=%s WHERE id=%s",
                    (body.get("title", ""), body.get("description", ""), body.get("sort_order", 0), feature_id))
        return {"ok": True}
    finally:
        conn.close()


@_admin.delete("/features/{feature_id}")
async def admin_features_delete(request: Request, feature_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM enterprise_features WHERE id = %s", (feature_id,))
        return {"ok": True}
    finally:
        conn.close()


# --- Comparisons ---

@_admin.get("/comparisons")
async def admin_comparisons_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, competitor, slug, meta_title, UNIX_TIMESTAMP(created_at) as created_at, UNIX_TIMESTAMP(updated_at) as updated_at FROM comparisons ORDER BY competitor")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.get("/comparisons/{slug}")
async def admin_comparisons_get(request: Request, slug: str) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM comparisons WHERE slug = %s", (slug,))
        row = cur.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


@_admin.post("/comparisons")
async def admin_comparisons_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO comparisons (competitor, slug, rows_data, meta_title, meta_description) VALUES (%s,%s,%s,%s,%s)",
                    (body.get("competitor", ""), body.get("slug", ""), json.dumps(body.get("rows", [])),
                     body.get("meta_title", ""), body.get("meta_description", "")))
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


@_admin.put("/comparisons/{slug}")
async def admin_comparisons_update(request: Request, slug: str) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE comparisons SET competitor=%s, rows_data=%s, meta_title=%s, meta_description=%s WHERE slug=%s",
                    (body.get("competitor", slug), json.dumps(body.get("rows", [])),
                     body.get("meta_title", ""), body.get("meta_description", ""), slug))
        return {"ok": True}
    finally:
        conn.close()


@_admin.delete("/comparisons/{slug}")
async def admin_comparisons_delete(request: Request, slug: str) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM comparisons WHERE slug = %s", (slug,))
        return {"ok": True}
    finally:
        conn.close()


# --- Pages ---

@_admin.get("/pages")
async def admin_pages_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, slug, title, meta_title, UNIX_TIMESTAMP(updated_at) as updated_at FROM pages ORDER BY slug")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@_admin.get("/pages/{slug}")
async def admin_pages_get(request: Request, slug: str) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM pages WHERE slug = %s", (slug,))
        row = cur.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


@_admin.post("/pages")
async def admin_pages_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO pages (slug, title, content, meta_title, meta_description) VALUES (%s,%s,%s,%s,%s)",
                    (body.get("slug", ""), body.get("title", ""), body.get("content", ""),
                     body.get("meta_title", ""), body.get("meta_description", "")))
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


@_admin.put("/pages/{slug}")
async def admin_pages_update(request: Request, slug: str) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE pages SET slug=%s, title=%s, content=%s, meta_title=%s, meta_description=%s WHERE slug=%s",
                    (body.get("slug", slug), body.get("title", ""), body.get("content", ""),
                     body.get("meta_title", ""), body.get("meta_description", ""), slug))
        return {"ok": True}
    finally:
        conn.close()


@_admin.delete("/pages/{slug}")
async def admin_pages_delete(request: Request, slug: str) -> dict[str, Any]:
    _require_admin(request)
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM pages WHERE slug = %s", (slug,))
        return {"ok": True}
    finally:
        conn.close()
_initialized = False


def _ensure_init() -> None:
    global _initialized
    if not _initialized:
        try:
            _init_db()
            _initialized = True
        except Exception:
            pass  # MySQL might not be available — endpoints will handle this
