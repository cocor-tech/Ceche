from __future__ import annotations

from typing import Any

import httpx


PARKED_PATTERNS = [
    "parked", "parking", "this domain is parked",
    "domain is not available", "domain coming soon",
    "coming soon", "under construction",
    "buy this domain", "domain for sale",
    "this domain may be for sale",
    "sedo", "afternic", "dan.com", "hugedomains",
    "this page is parked", "domain name is for sale",
    "the domain has been registered",
]


async def crawl_domain(domain: str, timeout: float = 8.0) -> dict[str, Any]:
    result: dict[str, Any] = {
        "crawled": False,
        "parked": None,
        "title": None,
        "description": None,
        "status_code": None,
        "content_length": 0,
        "error": None,
    }

    urls = [f"https://{domain}", f"http://{domain}"]

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
        headers={"User-Agent": "Ceche/1.0 (domain analysis)"},
    ) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                result["crawled"] = True
                result["status_code"] = resp.status_code
                text = resp.text
                result["content_length"] = len(text)

                title = _extract_title(text)
                if title:
                    result["title"] = title[:200]

                desc = _extract_meta(text, "description")
                if desc:
                    result["description"] = desc[:300]

                result["parked"] = _is_parked(text, result)
                return result
            except httpx.TimeoutException:
                continue
            except httpx.ConnectError:
                continue
            except Exception as e:
                result["error"] = str(e)
                continue

    if result["error"] is None:
        result["error"] = "Could not connect to domain"
    return result


def _extract_title(html: str) -> str | None:
    import re
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def _extract_meta(html: str, name: str) -> str | None:
    import re
    m = re.search(
        rf'<meta[^>]+(?:name|property)=["\'](?:og:)?{name}["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:og:)?{name}["\']',
        html, re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return None


def _is_parked(text: str, result: dict[str, Any]) -> bool:
    lower = text.lower()

    for pattern in PARKED_PATTERNS:
        if pattern in lower:
            return True

    if result.get("content_length", 0) < 200:
        return True

    title = result.get("title", "")
    if title and any(p in title.lower() for p in ["parked", "coming soon", "for sale", "buy this"]):
        return True

    return False
