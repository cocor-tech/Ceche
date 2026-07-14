from __future__ import annotations

from typing import Any

from ceche.infrastructure.ai.monitoring.audit import AIAuditLogger
from ceche.infrastructure.ai.monitoring.circuit import CircuitBreaker
from ceche.infrastructure.ai.monitoring.cost_tracker import CostTracker
from ceche.infrastructure.ai.monitoring.latency import LatencyMonitor


class AIHealthCheck:
    def __init__(
        self,
        provider: str,
        model: str,
        breaker: CircuitBreaker,
        cost: CostTracker,
        latency: LatencyMonitor,
        audit: AIAuditLogger,
    ) -> None:
        self._provider = provider
        self._model = model
        self._breaker = breaker
        self._cost = cost
        self._latency = latency
        self._audit = audit

    def status(self) -> dict[str, Any]:
        audit_stats = self._audit.stats()
        total = audit_stats["total_calls"]
        successes = audit_stats["successes"]
        return {
            "provider": self._provider,
            "model": self._model,
            "status": _health_status(self._breaker),
            "circuit_breaker": self._breaker.status(),
            "cost": self._cost.summary(),
            "latency": self._latency.overall(),
            "per_module_latency": self._latency.stats(),
            "calls": {
                "total": total,
                "success_rate": round(successes / max(1, total), 3),
            },
        }


def _health_status(breaker: CircuitBreaker) -> str:
    if breaker.is_open:
        return "degraded"
    return "healthy"
