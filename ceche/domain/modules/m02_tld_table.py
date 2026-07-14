from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule

TLD_FILE = Path(__file__).resolve().parent.parent / "data" / "tld_scores.json"

_WEIGHT_PROFILES: list[tuple[float, str, str]] = [
    (10.0, "tier_10", "Premium (.com)"),
    (9.0, "tier_09", "High (.net)"),
    (8.5, "tier_085", "High (.io, .ai)"),
    (8.0, "tier_08", "High (.co, .de, .edu, .org, .xxx)"),
    (7.5, "tier_075", "Upper-Mid (.app, .it, .xyz)"),
    (7.0, "tier_07", "Mid (.us, .tv, .me, .cc, .to, .tech)"),
    (6.5, "tier_065", "Mid (.world)"),
    (6.0, "tier_06", "Lower-Mid (.eu, .sh, .ca, .wiki, .pro, etc.)"),
    (5.0, "tier_05", "Low (.asia, .africa, .news, .site)"),
    (4.5, "tier_045", "Low (.ltd)"),
    (4.0, "tier_04", "Budget (.cloud, .blog, .fun, .live, etc.)"),
    (3.5, "tier_035", "Budget (.art)"),
    (3.0, "tier_03", "Budget (.network, .lgbt, .bio)"),
    (2.0, "tier_02", "Deep Budget (.agency, .lol, .one, .biz)"),
    (1.0, "tier_01", "Minimal (.icu)"),
    (0.2, "tier_00", "Default (all other TLDs)"),
]

_TIER_LABELS: dict[str, str] = {
    p[1]: p[2] for p in _WEIGHT_PROFILES
}


def _load_scores() -> tuple[dict[str, float], float]:
    with TLD_FILE.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    default = float(data.pop("_default", 0.2))
    scores: dict[str, float] = {}
    for key, raw in data.items():
        scores[key] = float(raw)
    return scores, default


_SCORES, _DEFAULT = _load_scores()


class M2TLDTable(BaseModule):
    name = "m2_tld_table"

    def __init__(self) -> None:
        self._scores: dict[str, float] = _SCORES
        self._default: float = _DEFAULT

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        tld: str | None = context.get("tld")
        if not tld:
            return ModuleResult.error(self.name, "no tld in context")

        clean_tld = tld.lower().lstrip(".")
        score = self._scores.get(clean_tld, self._default)

        profile = self._resolve_profile(score)
        label = _TIER_LABELS.get(profile, "Unknown")

        return ModuleResult(
            module_name=self.name,
            value=score,
            confidence=1.0,
            data={
                "tld": clean_tld,
                "tld_score": score,
                "weight_profile": profile,
                "tier_label": label,
            },
            status=ModuleStatus.SUCCESS,
        )

    @staticmethod
    def _resolve_profile(score: float) -> str:
        for threshold, profile, _ in _WEIGHT_PROFILES:
            if score >= threshold - 0.001:
                return profile
        return "tier_00"
