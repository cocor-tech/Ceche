from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

_admin = APIRouter(prefix="/admin/api")

# Simple JWT-like token using HMAC. In production, use a proper JWT library.
_SECRET = os.getenv("CECHE_ADMIN_SECRET", secrets.token_hex(32))


def _make_token(user_id: int, role: str) -> str:
    payload = f"{user_id}:{role}:{int(time.time()) + 86400}"
    sig = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}:{sig}"


def _verify_token(token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(":")
        if len(parts) != 4:
            return None
        user_id, role, exp_str, sig = parts
        exp = int(exp_str)
        if exp < time.time():
            return None
        expected_sig = hmac.new(
            _SECRET.encode(), f"{user_id}:{role}:{exp_str}".encode(), hashlib.sha256,
        ).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        return {"user_id": int(user_id), "role": role, "exp": exp}
    except (ValueError, IndexError):
        return None


def _get_token(request: Request) -> dict[str, Any] | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return _verify_token(auth[7:])
    cookie = request.cookies.get("ceche_admin_token")
    if cookie:
        return _verify_token(cookie)
    return None


def _require_admin(request: Request) -> dict[str, Any]:
    token = _get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token


# --- Auth endpoints ---

class LoginRequest(BaseModel):
    email: str
    password: str


@_admin.post("/login")
async def admin_login(req: LoginRequest, response: Response) -> dict[str, Any]:
    # Simple auth — in production, query MySQL users table with bcrypt
    if req.email == "admin@ceche.app" and req.password == "admin123":
        token = _make_token(1, "admin")
        response.set_cookie(
            key="ceche_admin_token", value=token,
            httponly=True, max_age=86400, samesite="lax",
        )
        return {"token": token, "role": "admin"}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@_admin.post("/logout")
async def admin_logout(response: Response) -> dict[str, Any]:
    response.delete_cookie("ceche_admin_token")
    return {"ok": True}


@_admin.get("/verify")
async def admin_verify(request: Request) -> dict[str, Any]:
    token = _require_admin(request)
    return {"ok": True, "role": token["role"]}


# --- Stats endpoints ---

@_admin.get("/stats")
async def admin_stats(request: Request) -> dict[str, Any]:
    _require_admin(request)
    return {
        "total_appraisals": 0,
        "today_appraisals": 0,
        "avg_value": None,
        "top_domain": None,
    }


@_admin.get("/recent")
async def admin_recent(request: Request, limit: int = 10) -> list[dict[str, Any]]:
    _require_admin(request)
    return []


# --- Blog endpoints ---

@_admin.get("/blog")
async def admin_blog_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    return []


@_admin.post("/blog")
async def admin_blog_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


@_admin.get("/blog/{post_id}")
async def admin_blog_get(request: Request, post_id: int) -> dict[str, Any]:
    _require_admin(request)
    return {}


@_admin.put("/blog/{post_id}")
async def admin_blog_update(request: Request, post_id: int) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


@_admin.delete("/blog/{post_id}")
async def admin_blog_delete(request: Request, post_id: int) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


# --- Documentation endpoints ---

@_admin.get("/docs")
async def admin_docs_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    return []


@_admin.post("/docs")
async def admin_docs_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


@_admin.get("/docs/{doc_id}")
async def admin_docs_get(request: Request, doc_id: int) -> dict[str, Any]:
    _require_admin(request)
    return {}


@_admin.put("/docs/{doc_id}")
async def admin_docs_update(request: Request, doc_id: int) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


@_admin.delete("/docs/{doc_id}")
async def admin_docs_delete(request: Request, doc_id: int) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


# --- Settings endpoints ---

@_admin.get("/settings")
async def admin_settings_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    return []


@_admin.put("/settings/{key_name}")
async def admin_settings_update(request: Request, key_name: str) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


# --- API Keys endpoints ---

@_admin.get("/api-keys")
async def admin_api_keys_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    return []


@_admin.post("/api-keys")
async def admin_api_keys_create(request: Request) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True, "key": ""}


@_admin.delete("/api-keys/{key_id}")
async def admin_api_keys_delete(request: Request, key_id: int) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


# --- Rate limits endpoints ---

@_admin.get("/rate-limits")
async def admin_rate_limits_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    return []


@_admin.put("/rate-limits/{tier}")
async def admin_rate_limits_update(request: Request, tier: str) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


# --- Users endpoints ---

@_admin.get("/users")
async def admin_users_list(request: Request) -> list[dict[str, Any]]:
    _require_admin(request)
    return []


@_admin.post("/users")
async def admin_users_invite(request: Request) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


@_admin.delete("/users/{user_id}")
async def admin_users_delete(request: Request, user_id: int) -> dict[str, Any]:
    _require_admin(request)
    return {"ok": True}


# --- Domains endpoint ---

@_admin.get("/domains")
async def admin_domains_list(
    request: Request, page: int = 1, per_page: int = 50,
    search: str = "", tld: str = "", source: str = "",
) -> dict[str, Any]:
    _require_admin(request)
    return {"domains": [], "total": 0, "page": page, "per_page": per_page}
