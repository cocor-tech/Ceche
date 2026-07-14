from __future__ import annotations

import httpx

from ceche.domain.models import TrademarkResult
from ceche.domain.ports import TrademarkPort


class EUIPOAdapter(TrademarkPort):
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def check(self, term: str) -> TrademarkResult:
        return TrademarkResult(conflict=False, severity="none", marks=[])
