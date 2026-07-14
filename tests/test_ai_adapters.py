"""Tests for Layer 7 — Multi-Model Support."""

from __future__ import annotations

from ceche.infrastructure.ai.adapters.base import AIResponse
from ceche.infrastructure.ai.adapters.noop import NoOpAdapter
from ceche.infrastructure.ai.adapters.ollama import OllamaAdapter
from ceche.infrastructure.ai.selector import ModelSelector


class TestNoOpAdapter:
    async def test_returns_empty(self):
        adapter = NoOpAdapter()
        resp = await adapter.complete("test")
        assert resp.content == ""
        assert resp.model == "none"

    async def test_health_returns_false(self):
        adapter = NoOpAdapter()
        assert await adapter.health_check() is False

    def test_cost_is_zero(self):
        adapter = NoOpAdapter()
        assert adapter.cost_per_1k_input == 0.0


class TestAIResponse:
    def test_defaults(self):
        resp = AIResponse(content="hello", model="test")
        assert resp.content == "hello"
        assert resp.tokens_in == 0
        assert resp.cost_usd == 0.0


class TestModelSelector:
    def test_selects_best_for_cost_with_noop_only(self):
        selector = ModelSelector([NoOpAdapter()])
        chosen = selector.best_for_cost()
        assert isinstance(chosen, NoOpAdapter)

    def test_adapters_property(self):
        a = NoOpAdapter()
        selector = ModelSelector([a])
        assert len(selector.adapters) == 1

    async def test_select_falls_back_to_noop(self):
        selector = ModelSelector([NoOpAdapter()])
        chosen = await selector.select()
        assert isinstance(chosen, NoOpAdapter)


class TestOllamaAdapter:
    def test_cost_is_zero(self):
        a = OllamaAdapter(model="llama3")
        assert a.cost_per_1k_input == 0.0
        assert a.cost_per_1k_output == 0.0

    def test_model_name(self):
        a = OllamaAdapter(model="mistral")
        assert a.model_name == "mistral"

    async def test_health_unreachable_returns_false(self):
        a = OllamaAdapter(base_url="http://localhost:19999")
        assert await a.health_check() is False

    async def test_complete_unreachable_returns_empty(self):
        a = OllamaAdapter(base_url="http://localhost:19999")
        resp = await a.complete("test")
        assert resp.content == ""
        assert resp.cost_usd == 0.0
