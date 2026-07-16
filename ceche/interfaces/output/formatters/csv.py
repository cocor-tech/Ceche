from __future__ import annotations

import csv
import io
from typing import Any

from ceche.domain.result import AppraisalResult

_COLUMNS = [
    "domain",
    "estimated_value",
    "range_low",
    "range_high",
    "confidence",
    "completeness_ratio",
    "tld_score",
    "weight_profile",
    "registered",
    "age_years",
    "word_count",
    "m6_result",
    "modules_success",
    "modules_skipped",
    "modules_unavailable",
    "modules_not_found",
]


def to_csv(results: list[AppraisalResult]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_COLUMNS)

    for r in results:
        m1 = r.modules.get("m1_rdap", {})
        m6 = r.modules.get("m6_segmenter", {})
        m12 = r.modules.get("m12_authority", {})

        ms_success = sum(
            1 for m in r.modules.values() if m.get("status") == "SUCCESS"
        )
        ms_skipped = sum(
            1 for m in r.modules.values() if m.get("status") == "SKIPPED"
        )
        ms_unavail = sum(
            1 for m in r.modules.values() if m.get("status") == "UNAVAILABLE"
        )
        ms_notfound = sum(
            1 for m in r.modules.values() if m.get("status") == "NOT_FOUND"
        )

        writer.writerow([
            r.domain,
            _f(r.estimated_value),
            _f(r.range_low),
            _f(r.range_high),
            r.confidence or "",
            _f(r.completeness_ratio),
            _f(r.tld_score),
            r.weight_profile or "",
            m1.get("registered", ""),
            _f(m12.get("age_years")),
            _f(m6.get("word_count")),
            m6.get("result", ""),
            ms_success,
            ms_skipped,
            ms_unavail,
            ms_notfound,
        ])

    return buf.getvalue()


def _f(v: Any) -> str:
    if v is None:
        return ""
    return str(v)
