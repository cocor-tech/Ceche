from __future__ import annotations


class CostController:
    def __init__(self, per_domain_budget: float = 0.01, daily_budget: float = 1.00) -> None:
        self._per_domain = per_domain_budget
        self._daily = daily_budget
        self._spent_today = 0.0
        self._domain_spent: dict[str, float] = {}

    def can_spend(self, domain: str, estimated: float) -> bool:
        if self._spent_today + estimated > self._daily:
            return False
        current = self._domain_spent.get(domain, 0.0)
        return current + estimated <= self._per_domain

    def track(self, domain: str, actual: float) -> None:
        self._spent_today += actual
        self._domain_spent[domain] = self._domain_spent.get(domain, 0.0) + actual

    def reset_domain(self, domain: str) -> None:
        self._domain_spent.pop(domain, None)

    @property
    def spent_today(self) -> float:
        return self._spent_today

    @property
    def daily_budget(self) -> float:
        return self._daily

    @property
    def per_domain_budget(self) -> float:
        return self._per_domain
