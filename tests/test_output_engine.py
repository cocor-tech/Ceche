"""Tests for Phase 3 — Output Engine, filters, CSV, JSONL."""

from __future__ import annotations

import csv
import io
import json

from ceche.domain.result import AppraisalResult
from ceche.interfaces.output.engine import OutputEngine, OutputOptions
from ceche.interfaces.output.filters import FilterOptions, apply_filters
from ceche.interfaces.output.formatters.csv import to_csv
from ceche.interfaces.output.formatters.jsonl import to_jsonl


def _make_result(
    domain: str = "test.com",
    value: float | None = 1000.0,
    confidence: str = "medium",
    tld_score: float = 10.0,
    registered: bool = True,
    m6_result: str = "split_found",
    word_count: int | None = 2,
    age_years: float | None = 5.0,
) -> AppraisalResult:
    modules = {
        "m1_rdap": {"registered": registered, "status": "SUCCESS"},
        "m6_segmenter": {
            "result": m6_result, "word_count": word_count,
            "status": "SUCCESS",
        },
        "m12_authority": {"age_years": age_years, "status": "SUCCESS"},
        "m16_brandability": {"status": "SKIPPED",
            "reason": "M6 found a split"},
    }
    for i in range(3, 15):
        mname = f"m{i}"
        if mname not in modules:
            modules[mname] = {"status": "SUCCESS"}
    return AppraisalResult(
        domain=domain,
        estimated_value=value,
        range_low=(value or 0) * 0.5,
        range_high=(value or 0) * 1.5,
        confidence=confidence,
        completeness_ratio=0.8,
        tld_score=tld_score,
        weight_profile="tier_10",
        modules=modules,
        version="2.0.0",
        generated_at="2026-07-16T12:00:00+00:00",
    )


class TestFilterOptions:
    def test_min_value_filter(self) -> None:
        r1 = _make_result(domain="low.com", value=500.0)
        r2 = _make_result(domain="high.com", value=2000.0)
        opts = FilterOptions(min_value=1000.0)
        filtered = apply_filters([r1, r2], opts)
        assert len(filtered) == 1
        assert filtered[0].domain == "high.com"

    def test_max_value_filter(self) -> None:
        r1 = _make_result(domain="low.com", value=500.0)
        r2 = _make_result(domain="high.com", value=2000.0)
        opts = FilterOptions(max_value=1000.0)
        filtered = apply_filters([r1, r2], opts)
        assert len(filtered) == 1
        assert filtered[0].domain == "low.com"

    def test_tld_filter(self) -> None:
        r1 = _make_result(domain="a.com")
        r2 = _make_result(domain="b.io")
        opts = FilterOptions(tld="com")
        filtered = apply_filters([r1, r2], opts)
        assert len(filtered) == 1
        assert filtered[0].domain == "a.com"

    def test_confidence_filter(self) -> None:
        r1 = _make_result(domain="high.com", confidence="high")
        r2 = _make_result(domain="low.com", confidence="low")
        opts = FilterOptions(confidence="high")
        filtered = apply_filters([r1, r2], opts)
        assert len(filtered) == 1
        assert "high" in filtered[0].domain

    def test_registered_filter(self) -> None:
        r1 = _make_result(domain="reg.com", registered=True)
        r2 = _make_result(domain="unreg.com", registered=False)
        opts = FilterOptions(registered=True)
        filtered = apply_filters([r1, r2], opts)
        assert len(filtered) == 1
        assert filtered[0].domain == "reg.com"

    def test_unregistered_filter(self) -> None:
        r1 = _make_result(domain="reg.com", registered=True)
        r2 = _make_result(domain="unreg.com", registered=False)
        opts = FilterOptions(unregistered=True)
        filtered = apply_filters([r1, r2], opts)
        assert len(filtered) == 1
        assert filtered[0].domain == "unreg.com"

    def test_brandable_filter(self) -> None:
        r1 = _make_result(domain="keyword.com", m6_result="split_found")
        r2 = _make_result(domain="brandable.com", m6_result="no_split")
        opts = FilterOptions(brandable=True)
        filtered = apply_filters([r1, r2], opts)
        assert len(filtered) == 1
        assert filtered[0].domain == "brandable.com"

    def test_keyword_filter(self) -> None:
        r1 = _make_result(domain="keyword.com", m6_result="split_found")
        r2 = _make_result(domain="brandable.com", m6_result="no_split")
        opts = FilterOptions(keyword=True)
        filtered = apply_filters([r1, r2], opts)
        assert len(filtered) == 1
        assert filtered[0].domain == "keyword.com"

    def test_word_count_filter(self) -> None:
        r1 = _make_result(domain="one.com", word_count=1)
        r2 = _make_result(domain="two.com", word_count=2)
        opts = FilterOptions(word_count=1)
        filtered = apply_filters([r1, r2], opts)
        assert len(filtered) == 1
        assert filtered[0].domain == "one.com"

    def test_age_filter(self) -> None:
        r1 = _make_result(domain="old.com", age_years=10.0)
        r2 = _make_result(domain="new.com", age_years=2.0)
        opts = FilterOptions(min_age=5.0)
        filtered = apply_filters([r1, r2], opts)
        assert len(filtered) == 1
        assert filtered[0].domain == "old.com"

    def test_sort_by_value(self) -> None:
        r1 = _make_result(domain="low.com", value=100.0)
        r2 = _make_result(domain="high.com", value=1000.0)
        opts = FilterOptions(sort="value", sort_order="desc")
        filtered = apply_filters([r1, r2], opts)
        assert filtered[0].domain == "high.com"

    def test_sort_by_name(self) -> None:
        r1 = _make_result(domain="z.com")
        r2 = _make_result(domain="a.com")
        opts = FilterOptions(sort="name")
        filtered = apply_filters([r1, r2], opts)
        assert filtered[0].domain == "a.com"

    def test_limit_and_skip(self) -> None:
        results = [_make_result(domain=f"d{i}.com") for i in range(5)]
        opts = FilterOptions(skip=2, limit=2)
        filtered = apply_filters(results, opts)
        assert len(filtered) == 2
        assert filtered[0].domain == "d2.com"

    def test_multiple_filters(self) -> None:
        r1 = _make_result(domain="a.com", value=5000.0, registered=True)
        r2 = _make_result(domain="b.com", value=500.0, registered=False)
        r3 = _make_result(domain="c.com", value=20000.0, registered=True)
        opts = FilterOptions(min_value=1000.0, registered=True, sort="value")
        filtered = apply_filters([r1, r2, r3], opts)
        assert len(filtered) == 2
        assert filtered[0].domain == "a.com"


class TestOutputEngine:
    def test_process_applies_filters(self) -> None:
        r1 = _make_result(domain="low.com", value=100.0)
        r2 = _make_result(domain="high.com", value=2000.0)
        opts = OutputOptions(min_value=500.0)
        eng = OutputEngine([r1, r2], opts)
        processed = eng.process()
        assert len(processed) == 1
        assert processed[0].domain == "high.com"

    def test_render_json(self) -> None:
        r = _make_result()
        opts = OutputOptions(format="json")
        eng = OutputEngine([r], opts)
        output = eng.render()
        data = json.loads(output)
        assert len(data) == 1
        assert data[0]["domain"] == "test.com"

    def test_render_csv(self) -> None:
        r = _make_result()
        opts = OutputOptions(format="csv")
        eng = OutputEngine([r], opts)
        output = eng.render()
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["domain"] == "test.com"
        assert float(rows[0]["estimated_value"]) == 1000.0

    def test_render_jsonl(self) -> None:
        r = _make_result()
        opts = OutputOptions(format="jsonl")
        eng = OutputEngine([r], opts)
        output = eng.render()
        lines = output.strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["domain"] == "test.com"

    def test_render_multiple_results(self) -> None:
        results = [_make_result(domain=f"d{i}.com") for i in range(3)]
        opts = OutputOptions(format="json")
        eng = OutputEngine(results, opts)
        output = eng.render()
        data = json.loads(output)
        assert len(data) == 3

    def test_write_to_string(self) -> None:
        r = _make_result()
        opts = OutputOptions(format="json")
        eng = OutputEngine([r], opts)
        text = eng.render()
        assert "test.com" in text


class TestCSVFormatter:
    def test_csv_columns(self) -> None:
        r = _make_result()
        output = to_csv([r])
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 1
        assert "domain" in reader.fieldnames
        assert "estimated_value" in reader.fieldnames
        assert "confidence" in reader.fieldnames
        assert "age_years" in reader.fieldnames
        assert "word_count" in reader.fieldnames

    def test_csv_multiple_domains(self) -> None:
        r1 = _make_result(domain="a.com", value=100.0)
        r2 = _make_result(domain="b.com", value=200.0)
        output = to_csv([r1, r2])
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 2


class TestJSONLFormatter:
    def test_jsonl_one_per_line(self) -> None:
        r1 = _make_result(domain="a.com")
        r2 = _make_result(domain="b.com")
        output = to_jsonl([r1, r2])
        lines = output.strip().split("\n")
        assert len(lines) == 2
        data = json.loads(lines[0])
        assert data["domain"] == "a.com"
        data = json.loads(lines[1])
        assert data["domain"] == "b.com"

    def test_jsonl_includes_modules(self) -> None:
        r = _make_result()
        output = to_jsonl([r])
        data = json.loads(output.strip())
        assert "modules" in data
        assert "m1_rdap" in data["modules"]
