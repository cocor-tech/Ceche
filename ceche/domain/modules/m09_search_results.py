from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus, SearchResult
from ceche.domain.modules.base import BaseModule
from ceche.domain.ports import SearchPort

_MULT_MAP: list[tuple[int, float]] = [
    (10000, 5.0),
    (1000, 3.0),
    (100, 2.0),
    (10, 1.3),
    (0, 1.0),
]


class M9SearchResults(BaseModule):
    name = "m9_search_results"

    def __init__(self, primary: SearchPort, backup: SearchPort | None = None) -> None:
        self._primary = primary
        self._backup = backup

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        domain: str | None = context.get("domain_name")
        if not domain:
            return ModuleResult.error(self.name, "no domain_name in context")

        result = await self._search(domain)

        multiplier = _resolve_multiplier(result.result_count or 0)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=1.0 if result.result_count is not None else 0.3,
            data={
                "result_count": result.result_count,
                "top_snippets": result.snippets,
                "competing_tld": result.competing_tld,
                "multiplier": multiplier,
            },
            status=ModuleStatus.SUCCESS,
        )

    async def _search(self, domain: str) -> SearchResult:
        try:
            return await self._primary.search(domain)
        except Exception:
            pass

        if self._backup:
            try:
                return await self._backup.search(domain)
            except Exception:
                pass

        return SearchResult(result_count=None, snippets=[], competing_tld=False)


def _resolve_multiplier(count: int) -> float:
    for threshold, mult in _MULT_MAP:
        if count >= threshold:
            return mult
    return 1.0
