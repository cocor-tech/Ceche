from __future__ import annotations

from typing import Any

import httpx

from ceche.domain.models import ExternalServiceError, SearchResult
from ceche.domain.ports import SearchPort

_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveAdapter(SearchPort):
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._key = api_key
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str) -> SearchResult:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "X-Subscription-Token": self._key,
        }
        try:
            resp = await self._client.get(
                _BRAVE_URL,
                headers=headers,
                params={"q": query},
            )
        except httpx.RequestError as exc:
            raise ExternalServiceError(service="brave", message=str(exc)) from exc

        if resp.status_code == 429:
            return SearchResult(result_count=None, snippets=[], competing_tld=False)

        if resp.status_code != 200:
            raise ExternalServiceError(
                service="brave",
                message=f"status {resp.status_code}",
                status_code=resp.status_code,
            )

        data: dict[str, Any] = resp.json()
        web: dict[str, Any] = data.get("web", {})
        total = web.get("total_results")
        if isinstance(total, (int, float)):
            total = int(total)

        results: list[dict[str, Any]] = web.get("results", [])
        snippets: list[str] = []
        for r in results[:3]:
            desc = r.get("description", "")
            snippets.append(str(desc))

        competing = _detect_brave_conflict(query, results)

        return SearchResult(
            result_count=int(total) if isinstance(total, (int, float)) else None,
            snippets=snippets,
            competing_tld=competing,
        )


def _detect_brave_conflict(query: str, results: list[dict[str, Any]]) -> bool:
    parts = query.rsplit(".", 1)
    if len(parts) == 2:
        sld = parts[0].lower()
        for item in results:
            url = (item.get("url", "") or "").lower()
            if sld in url and query.lower() not in url:
                return True
    return False
