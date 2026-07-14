from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule

_MODULE_NAMES = [
    "m1_rdap",
    "m2_tld_table",
    "m3_length",
    "m4_word_count",
    "m5_pronounceability",
    "m6_segmenter",
    "m7_keyword_popularity",
    "m8_cpc",
    "m9_search_results",
    "m10_cross_tld",
    "m11_trademark",
    "m12_authority",
]

_SKIP_OK = frozenset(["m1_rdap", "m12_authority"])


class M13Confidence(BaseModule):
    name = "m13_confidence"

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        results: dict[str, dict[str, Any]] = {}
        total = 0
        with_data = 0

        for name in _MODULE_NAMES:
            key = f"result_{name}"
            result: dict[str, Any] | None = context.get(key)
            if result is None:
                continue

            total += 1
            status = result.get("status")

            if isinstance(status, ModuleStatus):
                status_str = status.name
            elif isinstance(status, str):
                status_str = status
            else:
                status_str = "unknown"

            if status_str in ("SUCCESS",):
                with_data += 1
            elif name in _SKIP_OK:
                pass

            results[name] = {"status": status_str}

        if total == 0:
            return ModuleResult(
                module_name=self.name,
                value=0.0,
                confidence=0.0,
                data={"completeness_ratio": 0.0, "label": "none"},
                status=ModuleStatus.SUCCESS,
            )

        ratio = with_data / total if total > 0 else 0.0

        if ratio >= 0.9:
            label = "high"
        elif ratio >= 0.7:
            label = "medium"
        elif ratio >= 0.5:
            label = "low"
        else:
            label = "very_low"

        return ModuleResult(
            module_name=self.name,
            value=ratio,
            confidence=1.0,
            data={
                "completeness_ratio": round(ratio, 2),
                "label": label,
                "modules_with_data": with_data,
                "applicable_modules": total,
            },
            status=ModuleStatus.SUCCESS,
        )
