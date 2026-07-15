"""Tests for BulkAppraisalEngine."""

from __future__ import annotations

import asyncio

from ceche.bulk_engine import BulkAppraisalEngine, BulkReport
from ceche.domain.result import AppraisalResult


class _MockEngine:
    def __init__(self, fail_on: set[str] | None = None, delay: float = 0.0) -> None:
        self._fail_on = fail_on or set()
        self._delay = delay
        self.calls: list[str] = []
        self.fresh_calls: list[bool] = []

    async def appraise(self, domain: str, fresh: bool = False) -> AppraisalResult:
        self.calls.append(domain)
        self.fresh_calls.append(fresh)
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if domain in self._fail_on:
            raise RuntimeError(f"mock failure for {domain}")
        return AppraisalResult(
            domain=domain,
            estimated_value=1000.0,
            range_low=500.0,
            range_high=2000.0,
            confidence="medium",
            completeness_ratio=0.8,
            tld_score=10.0,
            weight_profile="tier_08",
            modules={"m1_rdap": {"registered": True}},
        )


class TestBulkAppraisalEngine:
    async def test_single_domain(self) -> None:
        mock = _MockEngine()
        bulk = BulkAppraisalEngine(mock, concurrency=4)  # type: ignore[arg-type]
        report = await bulk.run(["example.com"])
        assert isinstance(report, BulkReport)
        assert report.summary.total == 1
        assert report.summary.succeeded == 1
        assert report.summary.failed == 0
        assert len(report.results) == 1
        assert report.results[0].domain == "example.com"
        assert len(report.failures) == 0

    async def test_multiple_domains(self) -> None:
        mock = _MockEngine()
        bulk = BulkAppraisalEngine(mock, concurrency=4)  # type: ignore[arg-type]
        domains = [f"domain{i}.com" for i in range(10)]
        report = await bulk.run(domains)
        assert report.summary.total == 10
        assert report.summary.succeeded == 10
        assert report.summary.failed == 0
        assert len(report.results) == 10
        assert len(report.failures) == 0

    async def test_failure_isolation(self) -> None:
        mock = _MockEngine(fail_on={"bad.com"})
        bulk = BulkAppraisalEngine(mock, concurrency=4)  # type: ignore[arg-type]
        domains = ["good.com", "bad.com", "ok.com"]
        report = await bulk.run(domains)
        assert report.summary.total == 3
        assert report.summary.succeeded == 2
        assert report.summary.failed == 1
        assert len(report.results) == 2
        assert len(report.failures) == 1
        assert report.failures[0].domain == "bad.com"
        assert "RuntimeError" in report.failures[0].error_type
        assert "mock failure" in report.failures[0].error_message

    async def test_all_failures(self) -> None:
        mock = _MockEngine(fail_on={"a.com", "b.com"})
        bulk = BulkAppraisalEngine(mock, concurrency=4)  # type: ignore[arg-type]
        report = await bulk.run(["a.com", "b.com"])
        assert report.summary.total == 2
        assert report.summary.succeeded == 0
        assert report.summary.failed == 2
        assert len(report.results) == 0
        assert len(report.failures) == 2

    async def test_empty_domain_list(self) -> None:
        mock = _MockEngine()
        bulk = BulkAppraisalEngine(mock, concurrency=4)  # type: ignore[arg-type]
        report = await bulk.run([])
        assert report.summary.total == 0
        assert report.summary.succeeded == 0
        assert report.summary.failed == 0

    async def test_concurrency_limited(self) -> None:
        mock = _MockEngine(delay=0.05)
        bulk = BulkAppraisalEngine(mock, concurrency=2)  # type: ignore[arg-type]
        domains = [f"d{i}.com" for i in range(6)]

        max_concurrent = 0
        running = 0
        lock = asyncio.Lock()

        original_appraise = mock.appraise

        async def tracked_appraise(domain: str, fresh: bool = False) -> AppraisalResult:
            nonlocal max_concurrent, running
            async with lock:
                running += 1
                max_concurrent = max(max_concurrent, running)
            result = await original_appraise(domain, fresh=fresh)
            async with lock:
                running -= 1
            return result

        mock.appraise = tracked_appraise  # type: ignore[method-assign]
        report = await bulk.run(domains)
        assert report.summary.succeeded == 6
        assert max_concurrent <= 2

    async def test_fresh_passed_through(self) -> None:
        mock = _MockEngine()
        bulk = BulkAppraisalEngine(mock, concurrency=4, fresh=True)  # type: ignore[arg-type]
        await bulk.run(["example.com"])
        assert mock.fresh_calls == [True]

    async def test_fresh_false_by_default(self) -> None:
        mock = _MockEngine()
        bulk = BulkAppraisalEngine(mock, concurrency=4)  # type: ignore[arg-type]
        await bulk.run(["example.com"])
        assert mock.fresh_calls == [False]

    async def test_report_summary_has_rate(self) -> None:
        mock = _MockEngine(delay=0.01)
        bulk = BulkAppraisalEngine(mock, concurrency=10)  # type: ignore[arg-type]
        report = await bulk.run([f"d{i}.com" for i in range(5)])
        assert report.summary.rate_domains_per_second > 0
        assert report.summary.duration_seconds > 0

    async def test_progress_callback(self) -> None:
        mock = _MockEngine(delay=0.01)
        bulk = BulkAppraisalEngine(mock, concurrency=4)  # type: ignore[arg-type]
        events: list[tuple[int, int, int]] = []

        def on_progress(total: int, succeeded: int, failed: int) -> None:
            events.append((total, succeeded, failed))

        await bulk.run([f"d{i}.com" for i in range(3)], on_progress=on_progress)
        assert len(events) == 3
        assert events[-1] == (3, 3, 0)

    async def test_progress_with_failures(self) -> None:
        mock = _MockEngine(fail_on={"bad.com"}, delay=0.01)
        bulk = BulkAppraisalEngine(mock, concurrency=4)  # type: ignore[arg-type]
        events: list[tuple[int, int, int]] = []

        def on_progress(total: int, succeeded: int, failed: int) -> None:
            events.append((total, succeeded, failed))

        await bulk.run(["good.com", "bad.com", "ok.com"], on_progress=on_progress)
        assert len(events) == 3
        assert events[-1] == (3, 2, 1)

    async def test_failure_captures_traceback(self) -> None:
        mock = _MockEngine(fail_on={"bad.com"})
        bulk = BulkAppraisalEngine(mock, concurrency=4)  # type: ignore[arg-type]
        report = await bulk.run(["bad.com"])
        assert len(report.failures) == 1
        assert report.failures[0].traceback_text is not None
        assert "RuntimeError" in report.failures[0].traceback_text
