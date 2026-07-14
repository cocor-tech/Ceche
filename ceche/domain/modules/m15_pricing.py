from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule

_TLD_BASE: dict[str, float] = {
    "tier_10": 5000.0,
    "tier_09": 2000.0,
    "tier_085": 2000.0,
    "tier_08": 2000.0,
    "tier_075": 800.0,
    "tier_07": 800.0,
    "tier_065": 500.0,
    "tier_06": 500.0,
    "tier_05": 200.0,
    "tier_045": 200.0,
    "tier_04": 200.0,
    "tier_035": 100.0,
    "tier_03": 100.0,
    "tier_02": 100.0,
    "tier_01": 100.0,
    "tier_00": 20.0,
}

_WEIGHTS_TIER_10 = {
    "m4_word_count": 0.30,
    "m3_length": 0.20,
    "m1_rdap": 0.15,
    "m7_keyword_popularity": 0.10,
    "m8_cpc": 0.10,
    "m5_pronounceability": 0.05,
    "m12_authority": 0.05,
    "m11_trademark": 0.05,
    "m10_cross_tld": 0.0,
}

_WEIGHTS_TIER_08 = {
    "m7_keyword_popularity": 0.25,
    "m8_cpc": 0.20,
    "m4_word_count": 0.15,
    "m5_pronounceability": 0.10,
    "m3_length": 0.10,
    "m1_rdap": 0.10,
    "m10_cross_tld": 0.05,
    "m11_trademark": 0.03,
    "m12_authority": 0.02,
}

_WEIGHTS_TIER_06 = {
    "m7_keyword_popularity": 0.30,
    "m8_cpc": 0.25,
    "m5_pronounceability": 0.15,
    "m10_cross_tld": 0.10,
    "m4_word_count": 0.10,
    "m1_rdap": 0.05,
    "m3_length": 0.05,
}

_WEIGHTS_TIER_04 = {
    "m8_cpc": 0.30,
    "m7_keyword_popularity": 0.25,
    "m10_cross_tld": 0.15,
    "m5_pronounceability": 0.10,
    "m4_word_count": 0.08,
    "m1_rdap": 0.05,
    "m3_length": 0.05,
    "m11_trademark": 0.02,
}

_WEIGHTS_TIER_01 = {
    "m8_cpc": 0.35,
    "m7_keyword_popularity": 0.25,
    "m10_cross_tld": 0.20,
    "m5_pronounceability": 0.10,
    "m4_word_count": 0.05,
    "m1_rdap": 0.03,
    "m3_length": 0.02,
}

_WEIGHTS_TIER_00 = {
    "m8_cpc": 0.40,
    "m7_keyword_popularity": 0.30,
    "m10_cross_tld": 0.20,
    "m5_pronounceability": 0.05,
    "m4_word_count": 0.03,
    "m3_length": 0.02,
}

_WEIGHTS_BRANDABLE = {
    "m5_pronounceability": 0.30,
    "m16_brandability": 0.25,
    "m3_length": 0.20,
    "m7_keyword_popularity": 0.10,
    "m8_cpc": 0.05,
    "m10_cross_tld": 0.05,
    "m2_tld_table": 0.03,
    "m11_trademark": 0.02,
}

_PROFILES = {
    "tier_10": _WEIGHTS_TIER_10,
    "tier_09": _WEIGHTS_TIER_08,
    "tier_085": _WEIGHTS_TIER_08,
    "tier_08": _WEIGHTS_TIER_08,
    "tier_075": _WEIGHTS_TIER_06,
    "tier_07": _WEIGHTS_TIER_06,
    "tier_065": _WEIGHTS_TIER_06,
    "tier_06": _WEIGHTS_TIER_06,
    "tier_05": _WEIGHTS_TIER_04,
    "tier_045": _WEIGHTS_TIER_04,
    "tier_04": _WEIGHTS_TIER_04,
    "tier_035": _WEIGHTS_TIER_04,
    "tier_03": _WEIGHTS_TIER_01,
    "tier_02": _WEIGHTS_TIER_01,
    "tier_01": _WEIGHTS_TIER_01,
    "tier_00": _WEIGHTS_TIER_00,
}

_UNAVAILABLE_WEIGHT_ALIASES = frozenset({"m1_rdap", "m12_authority"})


class M15Pricing(BaseModule):
    name = "m15_pricing"

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        weight_profile: str | None = context.get("weight_profile")
        if not weight_profile:
            return ModuleResult.error(self.name, "no weight_profile in context")

        base = _TLD_BASE.get(weight_profile, 2.0)

        is_no_split = context.get("m6_status") == "no_split"
        registered = context.get("registered", True)

        if is_no_split:
            weights = dict(_WEIGHTS_BRANDABLE)
        else:
            weights = dict(_PROFILES.get(weight_profile, _WEIGHTS_TIER_00))

        if not registered:
            for alias in _UNAVAILABLE_WEIGHT_ALIASES:
                weights.pop(alias, None)

        value = base
        breakdown: dict[str, float | None] = {}

        for name, weight in weights.items():
            if weight <= 0:
                continue
            mult_key = f"mult_{name}"
            mult: float | None = context.get(mult_key)
            if mult is not None and isinstance(mult, (int, float)) and mult > 0:
                contribution = (
                    1.0 + weight * (float(mult) - 1.0) if mult >= 1.0 else float(mult)
                )
                value *= contribution
                breakdown[name] = round(contribution, 4)
            else:
                breakdown[name] = None

        completeness: float = context.get("completeness_ratio", 1.0)
        if not isinstance(completeness, (int, float)):
            completeness = 1.0

        factor = (1.0 - completeness) * 0.5
        low = value * (1.0 - factor)
        high = value * (1.0 + factor)

        return ModuleResult(
            module_name=self.name,
            value=round(value, 2),
            confidence=completeness,
            data={
                "estimated_value": round(value, 2),
                "tld_base": base,
                "range": {"low": round(low, 2), "high": round(high, 2)},
                "completeness_ratio": round(completeness, 2),
                "weight_profile": weight_profile,
                "breakdown": breakdown,
            },
            status=ModuleStatus.SUCCESS,
        )
