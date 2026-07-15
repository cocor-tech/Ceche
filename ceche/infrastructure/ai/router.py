from __future__ import annotations

from typing import Any

from ceche.infrastructure.ai.adapters.base import BaseAIAdapter
from ceche.infrastructure.ai.adapters.generic import GenericAIAdapter

_MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "cost_in": 0.00014,
        "cost_out": 0.00028,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "cost_in": 0.00015,
        "cost_out": 0.00060,
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "cost_in": 0.00300,
        "cost_out": 0.00300,
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "cost_in": 0.00010,
        "cost_out": 0.00010,
    },
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "default_model": "abab6.5s-chat",
        "cost_in": 0.00100,
        "cost_out": 0.00100,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "cost_in": 0.00015,
        "cost_out": 0.00060,
    },
}

_DEFAULT_MODEL_OVERRIDES: dict[str, str] = {
    "deepseek": "deepseek-chat",
}


class ModelRouter:
    def __init__(self) -> None:
        self._adapters: dict[str, BaseAIAdapter] = {}
        self._module_assignments: dict[str, str] = {}
        self._default_provider = "none"

    def register_provider(self, provider_id: str, api_key: str) -> None:
        if provider_id not in _MODEL_REGISTRY:
            return
        cfg = _MODEL_REGISTRY[provider_id]
        model = _DEFAULT_MODEL_OVERRIDES.get(provider_id, cfg["default_model"])
        self._adapters[provider_id] = GenericAIAdapter(
            api_key=api_key,
            base_url=cfg["base_url"],
            model=model,
            provider_label=provider_id,
            cost_in=cfg["cost_in"],
            cost_out=cfg["cost_out"],
        )
        if not self._default_provider or self._default_provider == "none":
            self._default_provider = provider_id

    def assign_module(self, module: str, provider_id: str) -> None:
        self._module_assignments[module] = provider_id

    def assign_modules(self, modules: list[str], provider_id: str) -> None:
        for mod in modules:
            self._module_assignments[mod] = provider_id

    async def complete(
        self, module: str, prompt: str, system: str = "",
    ) -> str:
        provider = self._module_assignments.get(module, self._default_provider)
        adapter = self._adapters.get(provider)
        if adapter is None:
            return ""
        resp = await adapter.complete(prompt, system=system)
        return resp.content

    @property
    def enabled(self) -> bool:
        return len(self._adapters) > 0

    @property
    def providers(self) -> list[str]:
        return list(self._adapters.keys())

    @property
    def assignments(self) -> dict[str, str]:
        return dict(self._module_assignments)
