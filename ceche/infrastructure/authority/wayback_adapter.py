from __future__ import annotations

from typing import Any

import httpx


class WaybackAdapter:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=15.0)

    async def get_snapshots(self, domain: str) -> dict[str, Any]:
        url = f"http://web.archive.org/cdx/search/cdx?url={domain}&output=json&limit=100&fl=timestamp"
        try:
            resp = await self._client.get(url)
        except httpx.RequestError:
            return {"count": 0}

        try:
            data: list[Any] = resp.json()
        except (ValueError, TypeError):
            return {"count": 0}

        if not data or len(data) < 2:
            return {"count": 0}

        count = len(data) - 1
        first = data[1][0] if len(data) > 1 else None

        return {"count": count, "first_date": first}

    @staticmethod
    def parked_flag(snapshots: int, age_years: float | None) -> bool:
        if age_years is not None and age_years < 0.5:
            return False
        if age_years is not None and age_years >= 1.0:
            return snapshots <= 0
        return snapshots == 0

    @staticmethod
    def history_multiplier(snapshots: int) -> float:
        if snapshots >= 1000:
            return 3.0
        if snapshots >= 100:
            return 2.0
        if snapshots >= 10:
            return 1.5
        if snapshots > 0:
            return 1.2
        return 0.5
