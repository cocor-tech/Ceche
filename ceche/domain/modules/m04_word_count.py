from __future__ import annotations

import math
from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule

_WORD_MULT_MAP: list[tuple[int, float]] = [
    (1, 20.0),
    (2, 3.0),
    (3, 1.5),
    (4, 1.0),
]


class M4WordCount(BaseModule):
    name = "m4_word_count"

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        word_count: Any = context.get("word_count")

        if word_count is None:
            return ModuleResult(
                module_name=self.name,
                value=None,
                confidence=0.0,
                data={"reason": "no word count available — M6 likely returned no_split"},
                status=ModuleStatus.SKIPPED,
            )

        try:
            word_count = int(word_count)
        except (TypeError, ValueError):
            return ModuleResult.error(self.name, f"invalid word_count: {word_count}")

        if word_count < 1:
            return ModuleResult.error(self.name, f"word_count must be >= 1, got {word_count}")

        score = _compute_score(word_count)
        multiplier = _resolve_multiplier(word_count)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=1.0,
            data={
                "word_count": word_count,
                "score": round(score, 2),
                "multiplier": multiplier,
            },
            status=ModuleStatus.SUCCESS,
        )


def _compute_score(word_count: int) -> float:
    raw = 100.0 * math.exp(-0.5 * (word_count - 1))
    return max(0.0, min(100.0, raw))


def _resolve_multiplier(word_count: int) -> float:
    for threshold, mult in _WORD_MULT_MAP:
        if word_count <= threshold:
            return mult
    return 1.0
