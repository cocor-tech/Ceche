"""Tests for Layer 4 — Agent Orchestrator."""

from __future__ import annotations

from ceche.infrastructure.ai.orchestrator.agent import AgentOrchestrator
from ceche.infrastructure.ai.orchestrator.blender import blend_result
from ceche.infrastructure.ai.orchestrator.budget import CostController
from ceche.infrastructure.ai.orchestrator.policy import (
    RefinementPolicy,
    TriggerRule,
    build_default_policy,
)


class TestRefinementPolicy:
    def test_trigger_fires(self):
        rule = TriggerRule(
            module="m6", prompt_id="test",
            trigger=lambda ctx: ctx.get("word_count", 0) >= 4,
        )
        assert rule.evaluate({"word_count": 6}) is True

    def test_trigger_does_not_fire(self):
        rule = TriggerRule(
            module="m6", prompt_id="test",
            trigger=lambda ctx: ctx.get("word_count", 0) >= 4,
        )
        assert rule.evaluate({"word_count": 2}) is False

    def test_trigger_exception_returns_false(self):
        rule = TriggerRule(
            module="m6", prompt_id="test",
            trigger=lambda ctx: 1 / 0,  # will raise
        )
        assert rule.evaluate({}) is False

    def test_default_policy_has_rules(self):
        policy = build_default_policy()
        assert len(policy.rules) >= 6

    def test_active_rules(self):
        policy = RefinementPolicy()
        policy.add(TriggerRule(
            module="m6", prompt_id="id1",
            trigger=lambda ctx: ctx.get("x") == 1,
        ))
        policy.add(TriggerRule(
            module="m7", prompt_id="id2",
            trigger=lambda ctx: ctx.get("x") == 2,
        ))
        active = policy.active_rules({"x": 1})
        assert len(active) == 1
        assert active[0].prompt_id == "id1"


class TestBlender:
    def test_full_blend(self):
        result = blend_result(50.0, 0.3, 80.0, 0.8)
        assert result["value"] is not None
        assert result["confidence"] >= 0.3
        assert result["source"] in ("deterministic", "blended", "ai_refined")

    def test_high_confidence_original_capped(self):
        result = blend_result(50.0, 0.95, 80.0, 0.8)
        weight = result["blend_weight"]
        assert weight <= 0.5

    def test_ai_value_only(self):
        result = blend_result(None, 0.0, 80.0, 0.8)
        assert result["value"] == 80.0

    def test_original_value_only(self):
        result = blend_result(50.0, 0.0, None, 0.5)
        assert result["value"] == 50.0

    def test_preserves_original(self):
        result = blend_result(50.0, 0.5, 80.0, 0.8)
        assert result["original_value"] == 50.0
        assert result["ai_value"] == 80.0


class TestCostController:
    def test_within_budget(self):
        cc = CostController(per_domain_budget=0.01, daily_budget=1.00)
        assert cc.can_spend("test.com", 0.005) is True

    def test_exceeds_per_domain(self):
        cc = CostController(per_domain_budget=0.01, daily_budget=1.00)
        cc.track("test.com", 0.008)
        assert cc.can_spend("test.com", 0.005) is False

    def test_exceeds_daily(self):
        cc = CostController(per_domain_budget=0.10, daily_budget=0.01)
        assert cc.can_spend("test.com", 0.02) is False

    def test_track_updates_spent(self):
        cc = CostController()
        cc.track("test.com", 0.005)
        assert cc.spent_today == 0.005

    def test_reset_domain(self):
        cc = CostController(per_domain_budget=0.01)
        cc.track("test.com", 0.008)
        cc.reset_domain("test.com")
        assert cc.can_spend("test.com", 0.005) is True


class TestAgentOrchestrator:
    def test_disabled_when_no_ai(self):
        orch = AgentOrchestrator(ai=None)
        assert orch.enabled is False

    def test_policy_loaded_by_default(self):
        orch = AgentOrchestrator(ai=None)
        assert orch._policy is not None
        assert len(orch._policy.rules) >= 6

    async def test_refine_returns_none_when_disabled(self):
        orch = AgentOrchestrator(ai=None)
        result = await orch.refine_module("m6", {}, 50.0, 0.5)
        assert result is None

    def test_reset_clears_domain(self):
        orch = AgentOrchestrator(ai=None)
        orch._budget.track("test.com", 0.008)
        orch.reset_for_domain("test.com")
        assert orch._budget.can_spend("test.com", 0.005)
