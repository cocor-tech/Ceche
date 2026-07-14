from __future__ import annotations

import time
from typing import Any

import httpx

from ceche.infrastructure.ai.adapters.base import AIResponse, BaseAIAdapter


class OpenAIAdapter(BaseAIAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._key = api_key
        self._model = model
        self._url = "https://api.openai.com/v1/chat/completions"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def cost_per_1k_input(self) -> float:
        if "gpt-4o" in self._model and "mini" not in self._model:
            return 0.00250
        return 0.00015

    @property
    def cost_per_1k_output(self) -> float:
        if "gpt-4o" in self._model and "mini" not in self._model:
            return 0.01000
        return 0.00060

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
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self._url, headers=headers, json=payload)
        elapsed = int((time.monotonic() - start) * 1000)

        if resp.status_code != 200:
            return AIResponse(content="", model=self._model, latency_ms=elapsed)

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
            model=self._model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=self._compute_cost(tokens_in, tokens_out),
            latency_ms=elapsed,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self._key}"},
                )
            return resp.status_code == 200
        except Exception:
            return False
