from __future__ import annotations

from typing import Any

import httpx

_OPR_URL = "https://openpagerank.keywordseverywhere.com/v1/domains/bulk"


class OPRAdapter:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._key = api_key
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def lookup(self, domain: str) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        try:
            resp = await self._client.post(
                _OPR_URL,
                headers=headers,
                json={"domains": [domain], "include_history": False},
            )
        except httpx.RequestError:
            return {"rank": None, "score": None, "ref_domains": None}

        if resp.status_code != 200:
            return {"rank": None, "score": None, "ref_domains": None}

        try:
            data: dict[str, Any] = resp.json()
        except (ValueError, TypeError):
            return {"rank": None, "score": None, "ref_domains": None}

        results = data.get("results", [])
        if not results or not isinstance(results, list):
            return {"rank": None, "score": None, "ref_domains": None}

        r: dict[str, Any] = results[0] if isinstance(results[0], dict) else {}
        return {
            "rank": r.get("rank"),
            "score": r.get("open_page_rank"),
            "ref_domains": r.get("referring_domains"),
        }
