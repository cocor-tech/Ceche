from __future__ import annotations

import time
from typing import Any

import httpx

from ceche.infrastructure.ai.adapters.base import AIResponse, BaseAIAdapter


class GenericAIAdapter(BaseAIAdapter):
    """OpenAI-compatible adapter for DeepSeek, Kimi, GLM, MiniMax, OpenRouter, etc."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        provider_label: str = "generic",
        cost_in: float = 0.00015,
        cost_out: float = 0.00060,
    ) -> None:
        self._key = api_key
        self._model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._label = provider_label
        self._cost_in = cost_in
        self._cost_out = cost_out

    @property
    def model_name(self) -> str:
        return f"{self._label}/{self._model}"

    @property
    def cost_per_1k_input(self) -> float:
        return self._cost_in

    @property
    def cost_per_1k_output(self) -> float:
        return self._cost_out

    async def complete(self, prompt: str, system: str = "") -> AIResponse:
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": 150,
            "temperature": 0.1,
        }

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(self._url, headers=headers, json=payload)
        except Exception:
            return AIResponse(content="", model=self.model_name)

        elapsed = int((time.monotonic() - start) * 1000)

        if resp.status_code != 200:
            return AIResponse(content="", model=self.model_name, latency_ms=elapsed)

        data: dict[str, Any] = resp.json()
        choices = data.get("choices", [])
        content = ""
        if choices:
            content = str(choices[0].get("message", {}).get("content", ""))
        usage = data.get("usage", {})

        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))

        return AIResponse(
            content=content,
            model=self.model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=self._compute_cost(tokens_in, tokens_out),
            latency_ms=elapsed,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    self._url.rsplit("/", 1)[0] + "/models",
                    headers={"Authorization": f"Bearer {self._key}"},
                )
            return resp.status_code == 200
        except Exception:
            return False


PROVIDER_CONFIGS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "label": "deepseek",
        "cost_in": 0.00014,
        "cost_out": 0.00028,
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "label": "kimi",
        "cost_in": 0.00300,
        "cost_out": 0.00300,
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "label": "glm",
        "cost_in": 0.00010,
        "cost_out": 0.00010,
    },
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "model": "abab6.5s-chat",
        "label": "minimax",
        "cost_in": 0.00100,
        "cost_out": 0.00100,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
        "label": "openrouter",
        "cost_in": 0.00015,
        "cost_out": 0.00060,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "label": "groq",
        "cost_in": 0.00000,
        "cost_out": 0.00000,
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "label": "together",
        "cost_in": 0.00000,
        "cost_out": 0.00000,
    },
}

ENV_KEY_MAP = {
    "DEEPSEEK_API_KEY": "deepseek",
    "KIMI_API_KEY": "kimi",
    "MOONSHOT_API_KEY": "kimi",
    "GLM_API_KEY": "glm",
    "ZHIPU_API_KEY": "glm",
    "MINIMAX_API_KEY": "minimax",
    "OPENROUTER_API_KEY": "openrouter",
    "GROQ_API_KEY": "groq",
    "TOGETHER_API_KEY": "together",
}


def detect_providers() -> list[GenericAIAdapter]:
    import os
    adapters: list[GenericAIAdapter] = []
    for env_key, provider_id in ENV_KEY_MAP.items():
        api_key = os.getenv(env_key)
        if api_key:
            cfg: dict[str, Any] = PROVIDER_CONFIGS[provider_id]
            adapters.append(
                GenericAIAdapter(
                    api_key=api_key,
                    base_url=str(cfg["base_url"]),
                    model=str(cfg["model"]),
                    provider_label=str(cfg["label"]),
                    cost_in=float(cfg["cost_in"]),
                    cost_out=float(cfg["cost_out"]),
                )
            )
    return adapters
