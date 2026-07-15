from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.ai_refine import ai_refine_module
from ceche.domain.modules.base import BaseModule
from ceche.domain.ports import AIPort

CPC_FILE = Path(__file__).resolve().parent.parent / "data" / "cpc_keywords.json"

_TIER_MULT: dict[str, float] = {
    "elite": 5.0,
    "high": 3.0,
    "medium_high": 2.5,
    "medium": 2.0,
    "low": 1.5,
    "informational": 1.0,
}

_TIER_ORDER = ["elite", "high", "medium_high", "medium", "low", "informational"]


def _load_cpc() -> dict[str, str]:
    with CPC_FILE.open(encoding="utf-8") as f:
        data: Any = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"CPC file is not a dict: {type(data)}")
    return {str(k): str(v) for k, v in data.items()}


_CPC_MAP: dict[str, str] = _load_cpc()


class M8CPC(BaseModule):
    name = "m8_cpc"

    def __init__(self, ai: AIPort | None = None) -> None:
        self._cpc_map = _CPC_MAP
        self._ai = ai

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        words: Any = context.get("words")
        sld: str | None = context.get("sld", "")
        if not sld:
            sld = ""

        if not words:
            result = self._substring_scan(sld.lower())
            if result is not None:
                return result
            return ModuleResult(
                module_name=self.name,
                value=None,
                confidence=0.0,
                data={"reason": "no words in context — M6 likely returned no_split"},
                status=ModuleStatus.SKIPPED,
            )

        if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
            return ModuleResult.error(self.name, f"invalid words: {words}")

        match_word: str | None = None
        match_tier: str | None = None
        for word in words:
            tier = self._cpc_map.get(word.lower())
            if tier and _tier_rank(tier) < _tier_rank(match_tier):
                match_tier = tier
                match_word = word

        if match_tier is None or match_word is None:
            tier_label = "none"
            multiplier = 1.0
            confidence = 0.5
        else:
            tier_label = match_tier
            multiplier = _TIER_MULT.get(match_tier, 1.0)
            confidence = 1.0

        if tier_label == "none" and self._ai and words:
            result = await self._ai_refine(words, context)
            if result is not None:
                return result

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=confidence,
            data={
                "tier": tier_label,
                "match_word": match_word,
                "multiplier": multiplier,
            },
            status=ModuleStatus.SUCCESS,
        )

    def _substring_scan(self, sld: str) -> ModuleResult | None:
        best_tier: str | None = None
        best_word: str | None = None
        for word, tier in self._cpc_map.items():
            if len(word) >= 3 and word in sld and _tier_rank(tier) < _tier_rank(best_tier):
                best_tier = tier
                best_word = word
        if best_tier and best_word:
            mult = _TIER_MULT.get(best_tier, 1.0)
            return ModuleResult(
                module_name=self.name,
                value=mult,
                confidence=0.7,
                data={
                    "tier": best_tier,
                    "match_word": best_word,
                    "multiplier": mult,
                    "source": "substring_scan",
                },
                status=ModuleStatus.SUCCESS,
            )
        return None

    async def _ai_refine(self, words: list[str], context: dict[str, Any]) -> ModuleResult | None:
        for word in words:
            if len(word) < 3:
                continue
            prompt = (
                f"Term: {word}\n"
                f"Current classification: not in CPC map (default NONE)\n\n"
                f"What is the commercial intent? "
                f"TIER:ELITE,HIGH,MEDIUM_HIGH,MEDIUM,LOW,INFORMATIONAL,NONE\n"
                f"Respond ONLY with: TIER:X"
            )
            raw = await ai_refine_module(self._ai, self.name, context, prompt)
            if not raw:
                continue
            import re
            m = re.search(r"TIER\s*:\s*(\w+)", raw, re.IGNORECASE)
            if m:
                tier = m.group(1).lower()
                mult = _TIER_MULT.get(tier)
                if mult is not None:
                    return ModuleResult(
                        module_name=self.name,
                        value=mult,
                        confidence=0.7,
                        data={"tier": tier, "match_word": word, "multiplier": mult, "source": "ai"},
                        status=ModuleStatus.SUCCESS,
                    )
        return None


def _tier_rank(tier: str | None) -> int:
    if tier is None:
        return len(_TIER_ORDER)
    try:
        return _TIER_ORDER.index(tier)
    except ValueError:
        return len(_TIER_ORDER)
