"""Tests for Phase 4 — Persistence layer."""

from __future__ import annotations

from pathlib import Path

from ceche.domain.result import AppraisalResult
from ceche.infrastructure.persistence.store import AppraisalStore


def _make_result(domain: str = "test.com", value: float = 1000.0) -> AppraisalResult:
    return AppraisalResult(
        domain=domain,
        estimated_value=value,
        range_low=value * 0.5,
        range_high=value * 1.5,
        confidence="medium",
        completeness_ratio=0.8,
        tld_score=10.0,
        weight_profile="tier_10",
        modules={
            "m1_rdap": {"registered": True, "status": "SUCCESS"},
            "m6_segmenter": {"result": "split_found", "status": "SUCCESS"},
        },
        version="2.0.0",
        generated_at="2026-07-16T12:00:00+00:00",
    )


class TestAppraisalStore:
    def test_record_run_creates_entry(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        store = AppraisalStore(db)
        r = _make_result()
        run_id = store.record_run(
            ["test.com"], [r], [],
            fresh=False, version="2.0.0", command="test",
        )
        assert len(run_id) == 12
        runs = store.list_runs(days=365)
        assert len(runs) == 1
        assert runs[0]["command"] == "test"
        assert runs[0]["succeeded"] == 1

    def test_record_run_with_failures(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        store = AppraisalStore(db)
        r = _make_result()
        failures = [{"domain": "bad.com", "error_type": "ValueError", "error_message": "bad"}]
        run_id = store.record_run(
            ["good.com", "bad.com"], [r], failures,
            command="test",
        )
        assert run_id
        runs = store.list_runs()
        assert len(runs) == 1
        assert runs[0]["succeeded"] == 1
        assert runs[0]["failed"] == 1

    def test_list_runs_respects_days(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        store = AppraisalStore(db)
        store.record_run(["a.com"], [_make_result("a.com")], [], command="test")
        runs_now = store.list_runs(days=365)
        assert len(runs_now) == 1
        runs_far = store.list_runs(days=-1)
        assert len(runs_far) == 0

    def test_get_run_by_id(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        store = AppraisalStore(db)
        run_id = store.record_run(
            ["a.com"], [_make_result("a.com")], [], command="test",
        )
        run = store.get_run(run_id)
        assert run is not None
        assert run["id"] == run_id

    def test_get_domain_history(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        store = AppraisalStore(db)
        store.record_run(
            ["example.com"], [_make_result("example.com")], [], command="test",
        )
        history = store.get_domain_history("example.com", days=365)
        assert len(history) == 1
        assert history[0]["domain"] == "example.com"

    def test_get_stats(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        store = AppraisalStore(db)
        store.record_run(
            ["a.com", "b.com"],
            [_make_result("a.com", 100.0), _make_result("b.com", 200.0)],
            [], command="test",
        )
        stats = store.get_stats(days=365)
        assert stats["total_appraisals"] == 2
        assert stats["with_value"] == 2
        assert stats["avg_estimated_value"] == 150.0

    def test_clear_all_data(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        store = AppraisalStore(db)
        store.record_run(["a.com"], [_make_result("a.com")], [], command="test")
        store.clear()
        stats = store.get_stats()
        assert stats["total_appraisals"] == 0

    def test_clear_older_than_days(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        store = AppraisalStore(db)
        store.record_run(["a.com"], [_make_result("a.com")], [], command="test")
        store.clear(days=365)  # won't delete recent stuff
        stats = store.get_stats()
        assert stats["total_appraisals"] == 1  # still there because days=365 is in future

    def test_export_creates_file(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        store = AppraisalStore(db)
        store.record_run(["a.com"], [_make_result("a.com")], [], command="test")
        export_path = tmp_path / "export.json"
        store.export(str(export_path), days=365)
        assert export_path.is_file()
        import json
        data = json.loads(export_path.read_text())
        assert "runs" in data
        assert "appraisals" in data
