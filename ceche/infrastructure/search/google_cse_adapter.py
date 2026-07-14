from __future__ import annotations

from typing import Any

import httpx

from ceche.domain.models import ExternalServiceError, SearchResult
from ceche.domain.ports import SearchPort

_CSE_URL = "https://www.googleapis.com/customsearch/v1"


class GoogleCSEAdapter(SearchPort):
    def __init__(self, api_key: str, cx: str, client: httpx.AsyncClient | None = None) -> None:
        self._key = api_key
        self._cx = cx
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str) -> SearchResult:
        params: dict[str, str | int] = {"key": self._key, "cx": self._cx, "q": query}
        try:
            resp = await self._client.get(_CSE_URL, params=params)
        except httpx.RequestError as exc:
            raise ExternalServiceError(service="google_cse", message=str(exc)) from exc

        if resp.status_code == 403:
            return SearchResult(result_count=None, snippets=[], competing_tld=False)

        if resp.status_code != 200:
            raise ExternalServiceError(
                service="google_cse",
                message=f"status {resp.status_code}",
                status_code=resp.status_code,
            )

        data: dict[str, Any] = resp.json()
        search_info = data.get("searchInformation", {})
        total = int(search_info.get("totalResults", "0") or "0")
        items: list[dict[str, Any]] = data.get("items", [])
        snippets = [str(item.get("snippet", "")) for item in items[:3]]
        competing = _detect_tld_conflict(query, items)

        return SearchResult(
            result_count=total,
            snippets=snippets,
            competing_tld=competing,
        )


def _detect_tld_conflict(query: str, items: list[dict[str, Any]]) -> bool:
    parts = query.rsplit(".", 1)
    if len(parts) == 2:
        sld = parts[0].lower()
        for item in items:
            link = (item.get("link", "") or "").lower()
            if sld in link and query.lower() not in link:
                return True
    return False
