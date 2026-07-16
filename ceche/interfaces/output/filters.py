from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ceche.domain.result import AppraisalResult


@dataclass
class FilterOptions:
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


def apply_filters(
    results: list[AppraisalResult],
    opts: FilterOptions,
) -> list[AppraisalResult]:
    filtered = list(results)

    if opts.min_value is not None:
        filtered = [r for r in filtered if (r.estimated_value or 0) >= opts.min_value]
    if opts.max_value is not None:
        filtered = [r for r in filtered if (r.estimated_value or 0) <= opts.max_value]
    if opts.tld is not None:
        tld = opts.tld.lower().lstrip(".")
        filtered = [r for r in filtered if r.domain.endswith(f".{tld}")]
    if opts.confidence is not None:
        cl = opts.confidence.lower()
        filtered = [r for r in filtered if (r.confidence or "").lower() == cl]
    if opts.registered is True:
        filtered = [r for r in filtered if _is_registered(r)]
    if opts.unregistered is True:
        filtered = [r for r in filtered if not _is_registered(r)]
    if opts.brandable is True:
        filtered = [r for r in filtered if _m6_result(r) == "no_split"]
    if opts.keyword is True:
        filtered = [r for r in filtered if _m6_result(r) == "split_found"]
    if opts.word_count is not None:
        filtered = [
            r for r in filtered
            if _get_word_count(r) == opts.word_count
        ]
    if opts.min_age is not None:
        filtered = [r for r in filtered if (_get_age(r) or 0) >= opts.min_age]
    if opts.max_age is not None:
        filtered = [r for r in filtered if (_get_age(r) or 0) <= opts.max_age]

    filtered = apply_sort(filtered, opts.sort, opts.sort_order)
    filtered = apply_pagination(filtered, opts.skip, opts.limit)

    return filtered


def apply_sort(
    results: list[AppraisalResult],
    sort: str | None,
    order: str = "asc",
) -> list[AppraisalResult]:
    if sort is None:
        return results

    sort_map: dict[str, str] = {
        "value": "estimated_value",
        "name": "domain",
        "tld": "tld_score",
        "confidence": "confidence",
        "age": "age",
        "word_count": "word_count",
    }
    key_name = sort_map.get(sort, sort)
    reverse = order.lower() == "desc"

    def _key(r: AppraisalResult) -> Any:
        if key_name == "domain":
            return r.domain or ""
        if key_name == "estimated_value":
            return r.estimated_value if r.estimated_value is not None else -1
        if key_name == "tld_score":
            return r.tld_score if r.tld_score is not None else -1
        if key_name == "confidence":
            _levels = {"high": 4, "medium": 3, "low": 2, "very_low": 1}
            return _levels.get(r.confidence or "", 0)
        if key_name == "age":
            return _get_age(r) if _get_age(r) else -1
        if key_name == "word_count":
            return _get_word_count(r) if _get_word_count(r) else -1
        return ""

    return sorted(results, key=_key, reverse=reverse)


def apply_pagination(
    results: list[AppraisalResult],
    skip: int | None = None,
    limit: int | None = None,
) -> list[AppraisalResult]:
    if skip:
        results = results[skip:]
    if limit:
        results = results[:limit]
    return results


def _is_registered(r: AppraisalResult) -> bool:
    m1 = r.modules.get("m1_rdap", {})
    return m1.get("registered", True) is True


def _m6_result(r: AppraisalResult) -> str:
    m6 = r.modules.get("m6_segmenter", {})
    return m6.get("result", "") or ""


def _get_word_count(r: AppraisalResult) -> int | None:
    m6 = r.modules.get("m6_segmenter", {})
    return m6.get("word_count")


def _get_age(r: AppraisalResult) -> float | None:
    m12 = r.modules.get("m12_authority", {})
    return m12.get("age_years")
