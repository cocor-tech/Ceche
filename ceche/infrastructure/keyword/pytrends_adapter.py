from __future__ import annotations

import asyncio
import logging

from ceche.domain.ports import KeywordPopularityPort

logger = logging.getLogger(__name__)
_CONCURRENCY = asyncio.Semaphore(2)


class PytrendsAdapter(KeywordPopularityPort):
    async def get_popularity(self, term: str) -> float:
        async with _CONCURRENCY:
            try:
                return await asyncio.to_thread(self._get_popularity_sync, term)
            except Exception:
                logger.debug("pytrends failed for %r", term, exc_info=True)
                return 0.0

    @staticmethod
    def _get_popularity_sync(term: str) -> float:
        from pytrends.request import TrendReq

        pytrends = TrendReq(timeout=10)
        pytrends.build_payload(
            kw_list=[term],
            timeframe="today 12-m",
            geo="",
        )
        data = pytrends.interest_over_time()
        if data is None or data.empty:
            return 0.0

        values = data[term].dropna()
        if values.empty:
            return 0.0

        return round(float(values.max()), 2)
