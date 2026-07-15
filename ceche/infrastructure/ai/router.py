from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ceche.infrastructure.ai.adapters.base import BaseAIAdapter
from ceche.infrastructure.ai.adapters.generic import GenericAIAdapter


@dataclass
class ModelSpec:
    provider: str
    model: str
    temperature: float = 0.1
    max_tokens: int = 150

    def clone_with(self, **kwargs: Any) -> ModelSpec:
        return ModelSpec(
            provider=kwargs.get("provider", self.provider),
            model=kwargs.get("model", self.model),
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )


_PROVIDER_CFG: dict[str, dict[str, Any]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "cost_in": 0.00014,
        "cost_out": 0.00028,
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "cost_in": 0.00015,
        "cost_out": 0.00060,
        "models": ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"],
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "cost_in": 0.00012,
        "cost_out": 0.00012,
        "models": ["kimi-k2.7-code-highspeed", "kimi-k2.7-code", "kimi-k2.6"],
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "cost_in": 0.00005,
        "cost_out": 0.00005,
        "models": ["glm-5-flash", "glm-5"],
    },
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "cost_in": 0.00050,
        "cost_out": 0.00050,
        "models": ["minimax-m2", "abab7-chat-preview"],
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "cost_in": 0.00015,
        "cost_out": 0.00060,
        "models": [
            "openai/gpt-5.6-luna",
            "deepseek/deepseek-v4-flash",
            "anthropic/claude-sonnet-4-20250514",
        ],
    },
}


class ModelRouter:
    def __init__(self) -> None:
        self._adapters: dict[str, BaseAIAdapter] = {}
        self._module_specs: dict[str, ModelSpec] = {}
        self._default_spec: ModelSpec | None = None

    def register_provider(
        self,
        provider_id: str,
        api_key: str,
        model: str | None = None,
    ) -> None:
        if provider_id not in _PROVIDER_CFG:
            return
        cfg = _PROVIDER_CFG[provider_id]
        if model is None:
            model = cfg["models"][0]
        adapter = GenericAIAdapter(
            api_key=api_key,
            base_url=cfg["base_url"],
            model=model,
            provider_label=provider_id,
            cost_in=cfg["cost_in"],
            cost_out=cfg["cost_out"],
        )
        self._adapters[provider_id] = adapter
        if self._default_spec is None:
            self._default_spec = ModelSpec(provider=provider_id, model=model)

    def assign_spec(self, module: str, spec: ModelSpec) -> None:
        self._module_specs[module] = spec

    def assign_modules(
        self,
        modules: list[str],
        provider: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        if provider not in self._adapters:
            return
        cfg = _PROVIDER_CFG[provider]
        model_name = model or cfg["models"][0]
        spec = ModelSpec(
            provider=provider,
            model=model_name,
            temperature=temperature or 0.1,
            max_tokens=max_tokens or 150,
        )
        for mod in modules:
            self._module_specs[mod] = spec.clone_with()

    def set_default(
        self, provider: str, model: str | None = None,
        temperature: float = 0.1, max_tokens: int = 150,
    ) -> None:
        self._default_spec = ModelSpec(
            provider=provider,
            model=model or _PROVIDER_CFG[provider]["models"][0],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def get_spec(self, module: str) -> ModelSpec:
        fallback = ModelSpec(provider="none", model="none")
        return self._module_specs.get(module, self._default_spec or fallback)

    async def complete(
        self, module: str, prompt: str, system: str = "",
    ) -> str:
        spec = self.get_spec(module)
        adapter = self._adapters.get(spec.provider)
        if adapter is None:
            return ""
        resp = await adapter.complete(
            prompt, system=system,
            max_tokens=spec.max_tokens, temperature=spec.temperature,
        )
        return resp.content

    @property
    def enabled(self) -> bool:
        return len(self._adapters) > 0

    @property
    def providers(self) -> list[str]:
        return list(self._adapters.keys())

    def models_for(self, provider: str) -> list[str]:
        cfg: dict[str, Any] = _PROVIDER_CFG.get(provider, {})
        models: list[str] = cfg.get("models", [])
        return models

    @property
    def assignments(self) -> dict[str, str]:
        return {mod: f"{s.provider}/{s.model}" for mod, s in self._module_specs.items()}
