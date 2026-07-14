"""Tests for Layer 6 — Observability & Control."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ceche.infrastructure.ai.monitoring.audit import AIAuditLogger
from ceche.infrastructure.ai.monitoring.circuit import CircuitBreaker
from ceche.infrastructure.ai.monitoring.cost_tracker import CostTracker
from ceche.infrastructure.ai.monitoring.health import AIHealthCheck
from ceche.infrastructure.ai.monitoring.latency import LatencyMonitor


class TestAuditLogger:
    def test_log_and_query(self):
        db = str(Path(tempfile.mkdtemp()) / "ai_audit.db")
        logger = AIAuditLogger(db)
        logger.log(
            domain="test.com", module="m6", prompt_id="m06_disambiguate",
            prompt_version="1.0.0", provider="openai", model="gpt-4o-mini",
            prompt_text="Is this SINGLE?", response_text="SINGLE",
            latency_ms=100, cost_usd=0.001, success=True,
        )
        results = logger.query(domain="test.com")
        assert len(results) >= 1
        assert results[0]["module"] == "m6"

    def test_stats(self):
        db = str(Path(tempfile.mkdtemp()) / "ai_audit.db")
        logger = AIAuditLogger(db)
        logger.log(domain="a.com", module="m6", prompt_id="t", prompt_version="1",
                   provider="o", model="m", prompt_text="p", response_text="r",
                   success=True, cost_usd=0.001)
        logger.log(domain="b.com", module="m8", prompt_id="t", prompt_version="1",
                   provider="o", model="m", prompt_text="p", response_text="r",
                   success=False, cost_usd=0.0)
        stats = logger.stats()
        assert stats["total_calls"] == 2
        assert stats["successes"] == 1

    def test_truncates_long_content(self):
        db = str(Path(tempfile.mkdtemp()) / "ai_audit.db")
        logger = AIAuditLogger(db)
        long_text = "x" * 500
        logger.log(domain="test.com", module="m6", prompt_id="t", prompt_version="1",
                   provider="o", model="m", prompt_text=long_text, response_text=long_text)
        results = logger.query()
        assert len(results[0]["prompt_text"]) <= 210


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitBreaker.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=999)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        assert cb.state != CircuitBreaker.OPEN

    def test_record_success_resets(self):
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.status()["failure_count"] == 0

    def test_status_includes_metrics(self):
        cb = CircuitBreaker()
        s = cb.status()
        assert "state" in s
        assert "failure_count" in s


class TestCostTracker:
    def test_within_budget(self):
        ct = CostTracker(daily_budget=1.0, per_domain_budget=0.01)
        assert ct.can_spend("test.com", 0.005)

    def test_exceeds_daily(self):
        ct = CostTracker(daily_budget=0.001, per_domain_budget=0.01)
        assert not ct.can_spend("test.com", 0.002)

    def test_exceeds_per_domain(self):
        ct = CostTracker(per_domain_budget=0.005)
        ct.track("test.com", 0.004)
        assert not ct.can_spend("test.com", 0.002)

    def test_summary(self):
        ct = CostTracker(daily_budget=1.0)
        ct.track("a.com", 0.003)
        ct.track("b.com", 0.005)
        s = ct.summary()
        assert s["daily_spend"] == 0.008
        assert s["domains_appraised"] == 2

    def test_reset_domain(self):
        ct = CostTracker(per_domain_budget=0.005)
        ct.track("test.com", 0.004)
        ct.reset_domain("test.com")
        assert ct.can_spend("test.com", 0.005)


class TestLatencyMonitor:
    def test_record_and_stats(self):
        lm = LatencyMonitor()
        lm.record("m6", 100)
        lm.record("m6", 200)
        lm.record("m8", 300)
        stats = lm.stats()
        assert stats["m6"]["count"] == 2
        assert stats["m6"]["max_ms"] >= 200
        assert "m8" in stats

    def test_overall(self):
        lm = LatencyMonitor()
        lm.record("m6", 100)
        lm.record("m6", 200)
        overall = lm.overall()
        assert overall["avg_ms"] == 150.0


class TestAIHealthCheck:
    def test_status(self):
        cb = CircuitBreaker()
        ct = CostTracker()
        lm = LatencyMonitor()
        db = str(Path(tempfile.mkdtemp()) / "audit.db")
        audit = AIAuditLogger(db)
        health = AIHealthCheck("openai", "gpt-4o-mini", cb, ct, lm, audit)
        status = health.status()
        assert status["provider"] == "openai"
        assert status["status"] == "healthy"
