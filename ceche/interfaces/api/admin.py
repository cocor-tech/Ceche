from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import bcrypt
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

_admin = APIRouter(prefix="/admin/api")
_SECRET = os.getenv("CECHE_ADMIN_SECRET", secrets.token_hex(32))
_ADMIN_DB = str(Path.home() / ".config" / "ceche" / "admin.db")
_CECHE_DB = str(Path.home() / ".config" / "ceche" / "history.db")


def _get_db() -> sqlite3.Connection:
    Path(_ADMIN_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_ADMIN_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, name TEXT DEFAULT '', role TEXT DEFAULT 'editor', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS blog_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, slug TEXT UNIQUE NOT NULL, content TEXT NOT NULL, excerpt TEXT DEFAULT '', featured_image TEXT DEFAULT '', status TEXT DEFAULT 'draft', published_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS documentation_pages (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, slug TEXT UNIQUE NOT NULL, content TEXT NOT NULL, category TEXT DEFAULT '', sort_order INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS settings (key_name TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '', description TEXT DEFAULT '', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, key_hash TEXT NOT NULL, tier TEXT DEFAULT 'free', rate_limit INTEGER DEFAULT 60, active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_used TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS rate_limits (id INTEGER PRIMARY KEY AUTOINCREMENT, tier TEXT UNIQUE NOT NULL, requests_per_minute INTEGER DEFAULT 60, burst_size INTEGER DEFAULT 10, concurrent_limit INTEGER DEFAULT 5, enabled INTEGER DEFAULT 1)""")
    conn.row_factory = sqlite3.Row
    conn.commit()
    return conn


def _get_ceche_db() -> sqlite3.Connection | None:
    if not Path(_CECHE_DB).is_file():
        return None
    conn = sqlite3.connect(_CECHE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _make_token(user_id: int, role: str) -> str:
    payload = f"{user_id}:{role}:{int(time.time()) + 86400}"
    sig = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}:{sig}"


def _verify_token(token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(":")
        if len(parts) != 4: return None
        user_id, role, exp_str, sig = parts
        exp = int(exp_str)
        if exp < time.time(): return None
        expected = hmac.new(_SECRET.encode(), f"{user_id}:{role}:{exp_str}".encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected): return None
        return {"user_id": int(user_id), "role": role, "exp": exp}
    except (ValueError, IndexError):
        return None


def _get_token(request: Request) -> dict[str, Any] | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "): return _verify_token(auth[7:])
    cookie = request.cookies.get("ceche_admin_token")
    if cookie: return _verify_token(cookie)
    return None


def _require_admin(request: Request) -> dict[str, Any]:
    token = _get_token(request)
    if not token: raise HTTPException(status_code=401, detail="Unauthorized")
    return token


# --- Auth ---

class LoginRequest(BaseModel):
    email: str
    password: str


@_admin.post("/login")
async def admin_login(req: LoginRequest, response: Response) -> dict[str, Any]:
    conn = _get_db()
    row = conn.execute("SELECT id, password_hash, role FROM users WHERE email = ?", (req.email.strip().lower(),)).fetchone()
    if row is None:
        pw = os.getenv("CECHE_ADMIN_PASSWORD")
        if not pw or req.password != pw:
            conn.close(); raise HTTPException(status_code=401, detail="Invalid credentials")
        hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
        cur = conn.execute("INSERT INTO users (email, password_hash, name, role) VALUES (?,?,?,?)", (req.email.strip().lower(), hashed, "Admin", "admin"))
        conn.commit()
        uid = cur.lastrowid
        token = _make_token(uid, "admin")
        response.set_cookie(key="ceche_admin_token", value=token, httponly=True, max_age=86400, samesite="lax")
        conn.close()
        return {"token": token, "role": "admin", "first_run": True}
    if not bcrypt.checkpw(req.password.encode(), row["password_hash"].encode()):
        conn.close(); raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _make_token(row["id"], row["role"])
    response.set_cookie(key="ceche_admin_token", value=token, httponly=True, max_age=86400, samesite="lax")
    conn.close()
    return {"token": token, "role": row["role"]}


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
    cdb = _get_ceche_db()
    if not cdb:
        return {"total_appraisals": 0, "today_appraisals": 0, "avg_value": None, "top_domain": None}
    total = cdb.execute("SELECT COUNT(*) as c FROM appraisals").fetchone()["c"]
    today = cdb.execute("SELECT COUNT(*) as c FROM appraisals WHERE created_at >= ?", (int(time.time()) - 86400,)).fetchone()["c"]
    avg = cdb.execute("SELECT AVG(estimated_value) as v FROM appraisals WHERE estimated_value IS NOT NULL").fetchone()["v"]
    top = cdb.execute("SELECT domain, estimated_value FROM appraisals WHERE estimated_value IS NOT NULL ORDER BY estimated_value DESC LIMIT 1").fetchone()
    cdb.close()
    return {"total_appraisals": total, "today_appraisals": today, "avg_value": round(avg, 2) if avg else None, "top_domain": top["domain"] if top else None}


@_admin.get("/recent")
async def admin_recent(request: Request, limit: int = 10) -> list[dict[str, Any]]:
    _require_admin(request)
    cdb = _get_ceche_db()
    if not cdb: return []
    rows = cdb.execute("SELECT domain, estimated_value, confidence, source, created_at FROM appraisals ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    cdb.close()
    return [dict(r) for r in rows]


# --- Settings ---

@_admin.get("/settings")
async def admin_settings_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _get_db()
    rows = conn.execute("SELECT * FROM settings ORDER BY key_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@_admin.get("/settings/{key_name}")
async def admin_settings_get(request: Request, key_name: str) -> dict[str, Any]:
    _require_admin(request)
    conn = _get_db()
    row = conn.execute("SELECT * FROM settings WHERE key_name = ?", (key_name,)).fetchone()
    conn.close()
    if not row: return {"key_name": key_name, "value": ""}
    return dict(row)


@_admin.put("/settings/{key_name}")
async def admin_settings_update(request: Request, key_name: str) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    value = body.get("value", "")
    description = body.get("description", "")
    conn = _get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key_name, value, description) VALUES (?,?,?)", (key_name, value, description))
    conn.commit()
    conn.close()
    return {"ok": True}


@_admin.delete("/settings/{key_name}")
async def admin_settings_delete(request: Request, key_name: str) -> dict[str, Any]:
    _require_admin(request)
    conn = _get_db()
    conn.execute("DELETE FROM settings WHERE key_name = ?", (key_name,))
    conn.commit()
    conn.close()
    return {"ok": True}


# --- Blog ---

@_admin.get("/blog")
async def admin_blog_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _get_db()
    rows = conn.execute("SELECT id, title, slug, excerpt, status, published_at, created_at, updated_at FROM blog_posts ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@_admin.post("/blog")
async def admin_blog_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    slug = body.get("slug", body.get("title", "untitled").lower().replace(" ", "-").replace("/", "-")[:100])
    conn = _get_db()
    cur = conn.execute("INSERT INTO blog_posts (title, slug, content, excerpt, featured_image, status) VALUES (?,?,?,?,?,?)",
        (body.get("title", ""), slug, body.get("content", ""), body.get("excerpt", ""), body.get("featured_image", ""), body.get("status", "draft")))
    conn.commit()
    conn.close()
    return {"ok": True, "id": cur.lastrowid}


@_admin.get("/blog/{post_id}")
async def admin_blog_get(request: Request, post_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _get_db()
    row = conn.execute("SELECT * FROM blog_posts WHERE id = ?", (post_id,)).fetchone()
    conn.close()
    if not row: return {}
    return dict(row)


@_admin.put("/blog/{post_id}")
async def admin_blog_update(request: Request, post_id: int) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _get_db()
    conn.execute("UPDATE blog_posts SET title=?, slug=?, content=?, excerpt=?, featured_image=?, status=? WHERE id=?",
        (body.get("title", ""), body.get("slug", ""), body.get("content", ""), body.get("excerpt", ""), body.get("featured_image", ""), body.get("status", "draft"), post_id))
    if body.get("status") == "published":
        conn.execute("UPDATE blog_posts SET published_at = ? WHERE id = ? AND published_at IS NULL", (int(time.time()), post_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@_admin.delete("/blog/{post_id}")
async def admin_blog_delete(request: Request, post_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _get_db()
    conn.execute("DELETE FROM blog_posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# --- Documentation ---

@_admin.get("/docs")
async def admin_docs_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _get_db()
    rows = conn.execute("SELECT * FROM documentation_pages ORDER BY sort_order, title").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@_admin.post("/docs")
async def admin_docs_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    slug = body.get("slug", body.get("title", "untitled").lower().replace(" ", "-")[:100])
    conn = _get_db()
    cur = conn.execute("INSERT INTO documentation_pages (title, slug, content, category, sort_order) VALUES (?,?,?,?,?)",
        (body.get("title", ""), slug, body.get("content", ""), body.get("category", ""), body.get("sort_order", 0)))
    conn.commit()
    conn.close()
    return {"ok": True, "id": cur.lastrowid}


@_admin.get("/docs/{doc_id}")
async def admin_docs_get(request: Request, doc_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _get_db()
    row = conn.execute("SELECT * FROM documentation_pages WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if not row: return {}
    return dict(row)


@_admin.put("/docs/{doc_id}")
async def admin_docs_update(request: Request, doc_id: int) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _get_db()
    conn.execute("UPDATE documentation_pages SET title=?, slug=?, content=?, category=?, sort_order=? WHERE id=?",
        (body.get("title", ""), body.get("slug", ""), body.get("content", ""), body.get("category", ""), body.get("sort_order", 0), doc_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@_admin.delete("/docs/{doc_id}")
async def admin_docs_delete(request: Request, doc_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _get_db()
    conn.execute("DELETE FROM documentation_pages WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# --- API Keys ---

@_admin.get("/api-keys")
async def admin_api_keys_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _get_db()
    rows = conn.execute("SELECT id, name, tier, rate_limit, active, created_at, last_used FROM api_keys ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@_admin.post("/api-keys")
async def admin_api_keys_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    raw_key = "ceche_" + uuid.uuid4().hex[:24]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    conn = _get_db()
    conn.execute("INSERT INTO api_keys (name, key_hash, tier, rate_limit) VALUES (?,?,?,?)",
        (body.get("name", "Unnamed"), key_hash, body.get("tier", "free"), body.get("rate_limit", 60)))
    conn.commit()
    conn.close()
    return {"ok": True, "key": raw_key}


@_admin.delete("/api-keys/{key_id}")
async def admin_api_keys_delete(request: Request, key_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _get_db()
    conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# --- Rate Limits ---

@_admin.get("/rate-limits")
async def admin_rate_limits_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _get_db()
    conn.executescript("INSERT OR IGNORE INTO rate_limits (tier, requests_per_minute, burst_size, concurrent_limit) VALUES ('free',60,10,5),('pro',300,30,20),('enterprise',1000,100,50)")
    rows = conn.execute("SELECT * FROM rate_limits ORDER BY tier").fetchall()
    conn.commit()
    conn.close()
    return [dict(r) for r in rows]


@_admin.put("/rate-limits/{tier}")
async def admin_rate_limits_update(request: Request, tier: str) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    conn = _get_db()
    conn.execute("INSERT OR REPLACE INTO rate_limits (tier, requests_per_minute, burst_size, concurrent_limit, enabled) VALUES (?,?,?,?,?)",
        (tier, body.get("requests_per_minute", 60), body.get("burst_size", 10), body.get("concurrent_limit", 5), body.get("enabled", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


# --- Users ---

@_admin.get("/users")
async def admin_users_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    conn = _get_db()
    rows = conn.execute("SELECT id, email, name, role, created_at FROM users ORDER BY created_at ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@_admin.post("/users")
async def admin_users_invite(request: Request) -> dict[str, Any]:
    _require_admin(request)
    body = await request.json()
    hashed = bcrypt.hashpw(body.get("password", secrets.token_hex(8)).encode(), bcrypt.gensalt()).decode()
    conn = _get_db()
    try:
        cur = conn.execute("INSERT INTO users (email, password_hash, name, role) VALUES (?,?,?,?)",
            (body.get("email", ""), hashed, body.get("name", ""), body.get("role", "editor")))
        conn.commit()
        conn.close()
        return {"ok": True, "id": cur.lastrowid}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))


@_admin.delete("/users/{user_id}")
async def admin_users_delete(request: Request, user_id: int) -> dict[str, Any]:
    _require_admin(request)
    conn = _get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# --- Domains ---

@_admin.get("/domains")
async def admin_domains_list(request: Request, page: int = 1, per_page: int = 50, search: str = "", tld: str = "", source: str = "") -> dict[str, Any]:
    _require_admin(request)
    cdb = _get_ceche_db()
    if not cdb:
        return {"domains": [], "total": 0, "page": page, "per_page": per_page}
    where = []
    params: list[Any] = []
    if search:
        where.append("domain LIKE ?"); params.append(f"%{search}%")
    if tld:
        where.append("domain LIKE ?"); params.append(f"%.{tld}")
    if source:
        where.append("source = ?"); params.append(source)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = cdb.execute(f"SELECT COUNT(*) as c FROM appraisals{w}", params).fetchone()["c"]
    offset = (page - 1) * per_page
    rows = cdb.execute(f"SELECT id, domain, estimated_value, confidence, tld_score, weight_profile, source, created_at FROM appraisals{w} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [per_page, offset]).fetchall()
    cdb.close()
    return {"domains": [dict(r) for r in rows], "total": total, "page": page, "per_page": per_page}


@_admin.get("/domains/{domain_id}")
async def admin_domain_detail(request: Request, domain_id: int) -> dict[str, Any]:
    _require_admin(request)
    cdb = _get_ceche_db()
    if not cdb:
        return {}
    row = cdb.execute("SELECT * FROM appraisals WHERE id = ?", (domain_id,)).fetchone()
    cdb.close()
    if not row:
        return {}
    d = dict(row)
    if d.get("modules_json"):
        d["modules"] = json.loads(d["modules_json"])
    return d
