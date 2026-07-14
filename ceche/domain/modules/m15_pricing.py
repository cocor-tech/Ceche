from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule

_TLD_BASE: dict[str, float] = {
    "tier_10": 100.0,
    "tier_09": 50.0,
    "tier_085": 50.0,
    "tier_08": 50.0,
    "tier_075": 30.0,
    "tier_07": 30.0,
    "tier_065": 20.0,
    "tier_06": 20.0,
    "tier_05": 10.0,
    "tier_045": 10.0,
    "tier_04": 10.0,
    "tier_035": 5.0,
    "tier_03": 5.0,
    "tier_02": 5.0,
    "tier_01": 5.0,
    "tier_00": 2.0,
}


class M15Pricing(BaseModule):
    name = "m15_pricing"

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        tier: str | None = context.get("weight_profile")
        if not tier:
            return ModuleResult.error(self.name, "no weight_profile in context")

        base = _TLD_BASE.get(tier, 2.0)

        multiplier_names = [
            "m1_rdap",
            "m3_length",
            "m4_word_count",
            "m5_pronounceability",
            "m7_keyword_popularity",
            "m8_cpc",
            "m9_search_results",
            "m10_cross_tld",
            "m11_trademark",
            "m12_authority",
            "m16_brandability",
        ]

        product = base
        breakdown: dict[str, float | None] = {}

        for name in multiplier_names:
            key = f"mult_{name}"
            mult: float | None = context.get(key)
            if mult is not None and isinstance(mult, (int, float)) and mult > 0:
                product *= float(mult)
                breakdown[name] = float(mult)
            else:
                breakdown[name] = None

        completeness: float = context.get("completeness_ratio", 1.0)
        if not isinstance(completeness, (int, float)):
            completeness = 1.0

        factor = (1.0 - completeness) * 0.5
        low = product * (1.0 - factor)
        high = product * (1.0 + factor)

        return ModuleResult(
            module_name=self.name,
            value=round(product, 2),
            confidence=completeness,
            data={
                "estimated_value": round(product, 2),
                "tld_base": base,
                "range": {
                    "low": round(low, 2),
                    "high": round(high, 2),
                },
                "completeness_ratio": round(completeness, 2),
                "breakdown": breakdown,
            },
            status=ModuleStatus.SUCCESS,
        )
