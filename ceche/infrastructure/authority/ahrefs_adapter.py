from __future__ import annotations

from typing import Any

import httpx

_AHREFS_URL = "https://api.ahrefs.com/v3/public/domain-rating-free"


class AhrefsDRAdapter:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def lookup(self, domain: str) -> float | None:
        try:
            resp = await self._client.get(_AHREFS_URL, params={"target": domain})
        except httpx.RequestError:
            return None

        if resp.status_code != 200:
            return None

        try:
            data: dict[str, Any] = resp.json()
        except (ValueError, TypeError):
            return None

        dr: dict[str, Any] | None = data.get("domain_rating")
        if not isinstance(dr, dict):
            return None

        value = dr.get("domain_rating")
        if isinstance(value, (int, float)):
            return float(value)
        return None
