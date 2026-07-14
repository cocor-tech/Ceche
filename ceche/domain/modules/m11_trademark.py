from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus, TrademarkResult
from ceche.domain.modules.ai_refine import ai_refine_module
from ceche.domain.modules.base import BaseModule
from ceche.domain.ports import AIPort, TrademarkPort

_SEVERITY_MULT: dict[str, float] = {
    "none": 1.0,
    "partial": 0.5,
    "exact": 0.1,
}


class M11Trademark(BaseModule):
    name = "m11_trademark"

    def __init__(
        self,
        primary: TrademarkPort,
        backup: TrademarkPort | None = None,
        ai: AIPort | None = None,
    ) -> None:
        self._primary = primary
        self._backup = backup
        self._ai = ai

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        sld: str | None = context.get("sld")
        words: Any = context.get("words")

        if not sld:
            return ModuleResult.error(self.name, "no sld in context")

        worst_severity = "none"
        worst_marks: list[str] = []

        if isinstance(words, list) and all(isinstance(w, str) for w in words):
            for word in words:
                result = await self._check_word(word)
                if result.severity == "exact":
                    worst_severity = "exact"
                    worst_marks = result.marks
                    break
                if result.severity == "partial" and worst_severity != "exact":
                    worst_severity = "partial"
                    worst_marks = result.marks

        if worst_severity != "exact":
            full_result = await self._check_word(sld.lower())
            if full_result.severity == "exact" or (
                full_result.severity == "partial" and worst_severity == "none"
            ):
                worst_severity = full_result.severity
                worst_marks = full_result.marks

        tld = context.get("tld", "")
        wc = context.get("word_count")
        had_exact_match = worst_severity == "exact"
        if tld == "com" and wc == 1 and had_exact_match:
            worst_severity = "none"
            worst_marks = []

        if worst_severity == "none" and self._ai and isinstance(words, list):
            for word in words:
                if len(word) < 3:
                    continue
                prompt = (
                    f"Term: {word}\n"
                    f"Is this a registered trademark or likely brand? "
                    f"RISK:EXACT,HIGH,MEDIUM,LOW,NONE\n"
                    f"Respond ONLY with: RISK:X"
                )
                raw = await ai_refine_module(self._ai, self.name, context, prompt)
                if raw:
                    import re
                    m = re.search(r"RISK\s*:\s*(\w+)", raw, re.IGNORECASE)
                    if m and m.group(1).upper() in ("EXACT", "HIGH"):
                        worst_severity = m.group(1).lower()
                        worst_marks = [f"AI-detected: {word}"]
                        break

        multiplier = _SEVERITY_MULT.get(worst_severity, 1.0)
        context["is_canonical_brand"] = had_exact_match

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
