from __future__ import annotations

import math
from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule

_MULT_MAP: list[tuple[float, float]] = [
    (95.0, 15.0),
    (75.0, 8.0),
    (50.0, 2.0),
    (25.0, 1.2),
    (0.0, 1.0),
]


class M3Length(BaseModule):
    name = "m3_length"

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        sld: str | None = context.get("sld")
        if not sld:
            return ModuleResult.error(self.name, "no sld in context")

        raw_length = len(sld)

        score = _compute_score(raw_length)
        multiplier = _resolve_multiplier(score)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=1.0,
            data={
                "raw_length": raw_length,
                "score": round(score, 2),
                "multiplier": multiplier,
            },
            status=ModuleStatus.SUCCESS,
        )


def _compute_score(length: int) -> float:
    if length <= 0:
        return 0.0
    raw = 100.0 * (1.0 - 1.0 / (1.0 + math.exp(-0.8 * (length - 5))))
    return max(0.0, min(100.0, raw))


def _resolve_multiplier(score: float) -> float:
    for threshold, mult in _MULT_MAP:
        if score >= threshold:
            return mult
    return 1.0
