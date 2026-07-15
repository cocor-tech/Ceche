from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule

_SCARCITY_LENGTH: list[tuple[int, float]] = [
    (3, 13_000_000),
    (4, 1_000_000),
    (5, 100_000),
    (7, 10_000),
    (100, 1_000),
]

_SCARCITY_WORD: list[tuple[int, float]] = [
    (1, 5_000_000),
    (2, 8_000),
    (3, 1_000),
    (100, 100),
]

_TLD_MULT: dict[str, float] = {
    "tier_10": 1.0,
    "tier_09": 0.3,
    "tier_085": 0.4,
    "tier_08": 0.3,
    "tier_075": 0.2,
    "tier_07": 0.2,
    "tier_065": 0.15,
    "tier_06": 0.15,
    "tier_05": 0.05,
    "tier_045": 0.05,
    "tier_04": 0.05,
    "tier_035": 0.02,
    "tier_03": 0.02,
    "tier_02": 0.02,
    "tier_01": 0.01,
    "tier_00": 0.005,
}

_WEIGHTS_TIER_10 = {
    "m1_rdap": 0.14,
    "m7_keyword_popularity": 0.09,
    "m8_cpc": 0.09,
    "m9_search_results": 0.03,
    "m5_pronounceability": 0.05,
    "m12_authority": 0.05,
    "m11_trademark": 0.05,
    "m10_cross_tld": 0.0,
}

_WEIGHTS_TIER_08 = {
    "m7_keyword_popularity": 0.24,
    "m8_cpc": 0.19,
    "m9_search_results": 0.03,
    "m5_pronounceability": 0.10,
    "m1_rdap": 0.09,
    "m10_cross_tld": 0.05,
    "m11_trademark": 0.03,
    "m12_authority": 0.02,
}

_WEIGHTS_TIER_06 = {
    "m7_keyword_popularity": 0.29,
    "m8_cpc": 0.24,
    "m9_search_results": 0.03,
    "m5_pronounceability": 0.15,
    "m10_cross_tld": 0.10,
    "m1_rdap": 0.04,
}

_WEIGHTS_TIER_04 = {
    "m8_cpc": 0.29,
    "m7_keyword_popularity": 0.24,
    "m9_search_results": 0.02,
    "m10_cross_tld": 0.15,
    "m5_pronounceability": 0.10,
    "m1_rdap": 0.05,
    "m11_trademark": 0.02,
}

_WEIGHTS_TIER_01 = {
    "m8_cpc": 0.34,
    "m7_keyword_popularity": 0.24,
    "m9_search_results": 0.02,
    "m10_cross_tld": 0.20,
    "m5_pronounceability": 0.10,
    "m1_rdap": 0.03,
}

_WEIGHTS_TIER_00 = {
    "m8_cpc": 0.39,
    "m7_keyword_popularity": 0.29,
    "m9_search_results": 0.02,
    "m10_cross_tld": 0.20,
    "m5_pronounceability": 0.05,
}

_WEIGHTS_BRANDABLE = {
    "m5_pronounceability": 0.30,
    "m16_brandability": 0.25,
    "m7_keyword_popularity": 0.10,
    "m8_cpc": 0.05,
    "m10_cross_tld": 0.05,
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


def _lookup_tier(value: int, table: list[tuple[int, float]]) -> float:
    for threshold, amount in table:
        if value <= threshold:
            return amount
    return table[-1][1]


def _scarcity_base(
    sld: str,
    word_count: int | None,
    weight_profile: str,
    is_brandable: bool,
) -> float:
    length_tier = _lookup_tier(len(sld), _SCARCITY_LENGTH)
    if is_brandable or word_count is None:
        scarcity = length_tier
    else:
        word_tier = _lookup_tier(word_count, _SCARCITY_WORD)
        scarcity = max(length_tier, word_tier)
    tld_mult = _TLD_MULT.get(weight_profile, 0.005)
    return scarcity * tld_mult


class M15Pricing(BaseModule):
    name = "m15_pricing"

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        weight_profile: str | None = context.get("weight_profile")
        if not weight_profile:
            return ModuleResult.error(self.name, "no weight_profile in context")

        sld: str | None = context.get("sld")
        word_count: object = context.get("word_count")
        registered: bool = context.get("registered", True)
        is_no_split: bool = context.get("m6_status") == "no_split"

        wc: int | None = None
        if isinstance(word_count, (int, float)) and not is_no_split:
            wc = int(word_count)

        base = _scarcity_base(sld or "", wc, weight_profile, is_no_split)

        if is_no_split:
            weights = dict(_WEIGHTS_BRANDABLE)
        else:
            weights = dict(_PROFILES.get(weight_profile, _WEIGHTS_TIER_00))

        if not registered:
            for alias in _UNAVAILABLE_WEIGHT_ALIASES:
                weights.pop(alias, None)

        active_weights: dict[str, float] = {}
        for name, w in weights.items():
            mult_key = f"mult_{name}"
            raw = context.get(mult_key)
            if raw is not None and isinstance(raw, (int, float)):
                active_weights[name] = w

        if active_weights:
            total = sum(active_weights.values())
            normalized = {n: w / total for n, w in active_weights.items()}
        else:
            normalized = {}

        value = base
        breakdown: dict[str, float | None] = {}

        for name, weight in normalized.items():
            mult_key = f"mult_{name}"
            mult: float | None = context.get(mult_key)
            if mult is not None and isinstance(mult, (int, float)) and mult > 0:
                if name == "m12_authority" and mult >= 1.0:
                    contribution = 1.0 + weight * (float(mult) - 1.0)
                else:
                    contribution = (
                        float(mult) ** weight if mult >= 1.0 else float(mult)
                    )
                value *= contribution
                breakdown[name] = round(contribution, 4)

        for name in weights:
            if name not in breakdown:
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
                "scarcity_base": round(base, 2),
                "range": {"low": round(low, 2), "high": round(high, 2)},
                "completeness_ratio": round(completeness, 2),
                "weight_profile": weight_profile,
                "breakdown": breakdown,
            },
            status=ModuleStatus.SUCCESS,
        )
