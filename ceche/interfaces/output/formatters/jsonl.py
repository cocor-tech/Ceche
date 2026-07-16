from __future__ import annotations

import json

from ceche.domain.result import AppraisalResult


def to_jsonl(results: list[AppraisalResult]) -> str:
    lines: list[str] = []
    for r in results:
        mod_summary: dict[str, int] = {}
        for me in r.modules.values():
            s = me.get("status", "UNKNOWN")
            mod_summary[s] = mod_summary.get(s, 0) + 1
        entry = {
            "domain": r.domain,
            "estimated_value": r.estimated_value,
            "range": {"low": r.range_low, "high": r.range_high},
            "confidence": r.confidence,
            "completeness_ratio": r.completeness_ratio,
            "tld_score": r.tld_score,
            "weight_profile": r.weight_profile,
            "module_summary": mod_summary,
            "modules": r.modules,
        }
        lines.append(json.dumps(entry, default=str))
    return "\n".join(lines) + "\n"
