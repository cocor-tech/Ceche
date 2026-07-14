from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RefinementRule:
    module: str
    prompt_id: str
    tools: list[str] = field(default_factory=list)
    max_cost: float = 0.01

    def evaluate(self, context: dict[str, Any]) -> bool:
        return True


@dataclass
class TriggerRule(RefinementRule):
    trigger: Callable[[dict[str, Any]], bool] = field(default=lambda _: False)

    def evaluate(self, context: dict[str, Any]) -> bool:
        try:
            return self.trigger(context)
        except Exception:
            return False


@dataclass
class RefinementPolicy:
    rules: list[RefinementRule] = field(default_factory=list)

    def active_rules(self, context: dict[str, Any]) -> list[RefinementRule]:
        return [r for r in self.rules if r.evaluate(context)]

    def add(self, rule: RefinementRule) -> None:
        self.rules.append(rule)

    def sort_by_priority(self) -> None:
        priority = {
            "m6": 1, "m8": 2, "m11": 3, "m16": 4,
            "m5": 5, "m7": 6, "m13": 7, "m15": 8,
        }
        self.rules.sort(key=lambda r: priority.get(r.module, 99))


def build_default_policy() -> RefinementPolicy:
    policy = RefinementPolicy()

    policy.add(TriggerRule(
        module="m6", prompt_id="m06_disambiguate",
        tools=["word_frequency", "valid_word"],
        max_cost=0.005,
        trigger=lambda ctx: (ctx.get("word_count") or 0) >= 4,
    ))
    policy.add(TriggerRule(
        module="m6", prompt_id="m06_verify_nosplit",
        tools=["valid_word"],
        max_cost=0.003,
        trigger=lambda ctx: ctx.get("m6_status") == "no_split",
    ))
    policy.add(TriggerRule(
        module="m7", prompt_id="m07_keyword",
        tools=["keyword_popularity", "word_frequency"],
        max_cost=0.002,
        trigger=lambda ctx: (ctx.get("domain_score") or 100) < 10,
    ))
    policy.add(TriggerRule(
        module="m8", prompt_id="m08_cpc",
        tools=["cpc_lookup", "cpc_tier_rank"],
        max_cost=0.002,
        trigger=lambda ctx: (ctx.get("tier") or "none") == "none",
    ))
    policy.add(TriggerRule(
        module="m11", prompt_id="m11_trademark",
        tools=["known_trademark"],
        max_cost=0.002,
        trigger=lambda ctx: (ctx.get("severity") or "none") == "none",
    ))
    policy.add(TriggerRule(
        module="m13", prompt_id="m13_confidence",
        max_cost=0.001,
        trigger=lambda ctx: (ctx.get("completeness_ratio") or 1.0) < 0.8,
    ))
    policy.add(TriggerRule(
        module="m15", prompt_id="m15_pricing", max_cost=0.002,
    ))
    policy.add(TriggerRule(
        module="m16", prompt_id="m16_brandability",
        tools=["vowel_ratio", "bigram_frequency"],
        max_cost=0.003,
    ))

    policy.sort_by_priority()
    return policy
