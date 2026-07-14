from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule

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

    def __init__(self) -> None:
        self._cpc_map = _CPC_MAP

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
        else:
            tier_label = match_tier
            multiplier = _TIER_MULT.get(match_tier, 1.0)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=1.0 if match_tier else 0.5,
            data={
                "tier": tier_label,
                "match_word": match_word,
                "multiplier": multiplier,
            },
            status=ModuleStatus.SUCCESS,
        )


def _tier_rank(tier: str | None) -> int:
    if tier is None:
        return len(_TIER_ORDER)
    try:
        return _TIER_ORDER.index(tier)
    except ValueError:
        return len(_TIER_ORDER)
