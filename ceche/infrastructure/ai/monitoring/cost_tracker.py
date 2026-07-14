from __future__ import annotations

import time
from typing import Any


class CostTracker:
    def __init__(self, daily_budget: float = 1.00, per_domain_budget: float = 0.01) -> None:
        self._daily_budget = daily_budget
        self._per_domain = per_domain_budget
        self._spent_today = 0.0
        self._domain_spent: dict[str, float] = {}
        self._reset_day = int(time.strftime("%j"))

    def _check_reset(self) -> None:
        today = int(time.strftime("%j"))
        if today != self._reset_day:
            self._spent_today = 0.0
            self._domain_spent.clear()
            self._reset_day = today

    def can_spend(self, domain: str, estimated: float) -> bool:
        self._check_reset()
        if self._spent_today + estimated > self._daily_budget:
            return False
        current = self._domain_spent.get(domain, 0.0)
        return current + estimated <= self._per_domain

    def track(self, domain: str, actual: float) -> None:
        self._check_reset()
        self._spent_today += actual
        self._domain_spent[domain] = self._domain_spent.get(domain, 0.0) + actual

    def reset_domain(self, domain: str) -> None:
        self._domain_spent.pop(domain, None)

    def summary(self) -> dict[str, Any]:
        self._check_reset()
        domains = len(self._domain_spent)
        return {
            "daily_spend": round(self._spent_today, 4),
            "daily_budget": self._daily_budget,
            "daily_remaining": round(self._daily_budget - self._spent_today, 4),
            "per_domain_budget": self._per_domain,
            "domains_appraised": domains,
            "avg_cost_per_domain": round(self._spent_today / max(1, domains), 4),
        }
