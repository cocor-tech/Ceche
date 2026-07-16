from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ceche.domain.result import AppraisalResult
from ceche.interfaces.output.filters import FilterOptions, apply_filters
from ceche.interfaces.output.formatters import to_csv, to_jsonl


@dataclass
class OutputOptions:
    format: str = "json"
    output: str = ""
    min_value: float | None = None
    max_value: float | None = None
    tld: str | None = None
    confidence: str | None = None
    registered: bool | None = None
    unregistered: bool | None = None
    brandable: bool | None = None
    keyword: bool | None = None
    word_count: int | None = None
    min_age: float | None = None
    max_age: float | None = None
    sort: str | None = None
    sort_order: str = "asc"
    limit: int | None = None
    skip: int | None = None


class OutputEngine:
    """Post-processes and renders appraisal results."""

    def __init__(self, results: list[AppraisalResult], opts: OutputOptions | None = None) -> None:
        self._results = results
        self._opts = opts or OutputOptions()

    def process(self) -> list[AppraisalResult]:
        fopts = FilterOptions(
            min_value=self._opts.min_value,
            max_value=self._opts.max_value,
            tld=self._opts.tld,
            confidence=self._opts.confidence,
            registered=self._opts.registered,
            unregistered=self._opts.unregistered,
            brandable=self._opts.brandable,
            keyword=self._opts.keyword,
            word_count=self._opts.word_count,
            min_age=self._opts.min_age,
            max_age=self._opts.max_age,
            sort=self._opts.sort,
            sort_order=self._opts.sort_order,
            limit=self._opts.limit,
            skip=self._opts.skip,
        )
        return apply_filters(self._results, fopts)

    def render(self) -> str:
        processed = self.process()
        fmt = self._opts.format
        if fmt == "csv":
            return to_csv(processed)
        if fmt == "jsonl":
            return to_jsonl(processed)
        if fmt == "json":
            return _to_json(processed)
        return ""

    def write(self, text: str | None = None) -> None:
        if text is None:
            text = self.render()
        if self._opts.output:
            Path(self._opts.output).write_text(text)
        else:
            sys.stdout.write(text)


def _to_json(results: list[AppraisalResult]) -> str:
    entries: list[dict[str, Any]] = []
    for r in results:
        mod_summary: dict[str, int] = {}
        for me in r.modules.values():
            s = me.get("status", "UNKNOWN")
            mod_summary[s] = mod_summary.get(s, 0) + 1
        entries.append({
            "domain": r.domain,
            "estimated_value": r.estimated_value,
            "range": {"low": r.range_low, "high": r.range_high},
            "confidence": r.confidence,
            "completeness_ratio": r.completeness_ratio,
            "tld_score": r.tld_score,
            "weight_profile": r.weight_profile,
            "module_summary": mod_summary,
            "modules": r.modules,
        })
    return json.dumps(entries, indent=2, default=str) + "\n"
