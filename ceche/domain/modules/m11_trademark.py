from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus, TrademarkResult
from ceche.domain.modules.base import BaseModule
from ceche.domain.ports import TrademarkPort

_SEVERITY_MULT: dict[str, float] = {
    "none": 1.0,
    "partial": 0.5,
    "exact": 0.1,
}


class M11Trademark(BaseModule):
    name = "m11_trademark"

    def __init__(self, primary: TrademarkPort, backup: TrademarkPort | None = None) -> None:
        self._primary = primary
        self._backup = backup

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        words: Any = context.get("words")
        if not words:
            return ModuleResult(
                module_name=self.name,
                value=None,
                confidence=0.0,
                data={"reason": "no words in context"},
                status=ModuleStatus.SKIPPED,
            )

        if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
            return ModuleResult.error(self.name, f"invalid words: {words}")

        worst_severity = "none"
        worst_marks: list[str] = []

        for word in words:
            result = await self._check_word(word)
            if result.severity == "exact":
                worst_severity = "exact"
                worst_marks = result.marks
                break
            if result.severity == "partial" and worst_severity != "exact":
                worst_severity = "partial"
                worst_marks = result.marks

        multiplier = _SEVERITY_MULT.get(worst_severity, 1.0)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=1.0,
            data={
                "severity": worst_severity,
                "marks": worst_marks,
                "multiplier": multiplier,
            },
            status=ModuleStatus.SUCCESS,
        )

    async def _check_word(self, word: str) -> TrademarkResult:
        try:
            return await self._primary.check(word)
        except Exception:
            pass

        if self._backup:
            try:
                return await self._backup.check(word)
            except Exception:
                pass

        return TrademarkResult(conflict=False, severity="none", marks=[])
