from __future__ import annotations

import asyncio
from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule
from ceche.domain.ports import KeywordPopularityPort

_MULT_MAP: list[tuple[float, float]] = [
    (90.0, 8.0),
    (70.0, 5.0),
    (50.0, 3.0),
    (30.0, 2.0),
    (10.0, 1.5),
    (0.0, 1.0),
]


class M7KeywordPopularity(BaseModule):
    name = "m7_keyword_popularity"

    def __init__(self, port: KeywordPopularityPort) -> None:
        self._port = port

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        words: Any = context.get("words")
        if not words:
            return ModuleResult(
                module_name=self.name,
                value=None,
                confidence=0.0,
                data={"reason": "no words in context — M6 likely returned no_split"},
                status=ModuleStatus.SKIPPED,
            )

        if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
            return ModuleResult.error(self.name, f"invalid words: {words}")

        tasks = [self._port.get_popularity(w) for w in words]
        scores = await asyncio.gather(*tasks)

        domain_score = max(scores) if scores else 0.0
        multiplier = _resolve_multiplier(domain_score)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=min(1.0, len([s for s in scores if s > 0]) / max(1, len(scores))),
            data={
                "word_scores": {w: s for w, s in zip(words, scores, strict=False)},
                "domain_score": round(domain_score, 2),
                "multiplier": multiplier,
                "source": "pytrends",
            },
            status=ModuleStatus.SUCCESS,
        )


def _resolve_multiplier(score: float) -> float:
    for threshold, mult in _MULT_MAP:
        if score >= threshold:
            return mult
    return 1.0
