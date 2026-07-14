from __future__ import annotations

from ceche.infrastructure.ai.adapters.base import BaseAIAdapter
from ceche.infrastructure.ai.adapters.noop import NoOpAdapter
from ceche.infrastructure.ai.adapters.ollama import OllamaAdapter


class ModelSelector:
    def __init__(self, adapters: list[BaseAIAdapter]) -> None:
        self._adapters = adapters

    async def select(self, requires_tools: bool = False) -> BaseAIAdapter:
        for adapter in self._adapters:
            if isinstance(adapter, NoOpAdapter):
                continue
            if requires_tools and isinstance(adapter, OllamaAdapter):
                continue
            try:
                if await adapter.health_check():
                    return adapter
            except Exception:
                continue
        return NoOpAdapter()

    def best_for_cost(self) -> BaseAIAdapter:
        candidates = sorted(
            [a for a in self._adapters if not isinstance(a, NoOpAdapter)],
            key=lambda a: (a.cost_per_1k_input + a.cost_per_1k_output),
        )
        return candidates[0] if candidates else NoOpAdapter()

    def best_for_quality(self) -> BaseAIAdapter:
        quality_order = [
            "gpt-4o", "claude-3.5", "gpt-4o-mini", "claude-3", "llama3", "mistral",
        ]
        for name in quality_order:
            for adapter in self._adapters:
                if name in adapter.model_name.lower() and not isinstance(adapter, NoOpAdapter):
                    return adapter
        return self.best_for_cost()

    @property
    def adapters(self) -> list[BaseAIAdapter]:
        return self._adapters
