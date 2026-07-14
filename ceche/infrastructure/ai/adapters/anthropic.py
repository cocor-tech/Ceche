from __future__ import annotations

import time
from typing import Any

import httpx

from ceche.infrastructure.ai.adapters.base import AIResponse, BaseAIAdapter


class AnthropicAdapter(BaseAIAdapter):
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307") -> None:
        self._key = api_key
        self._model = model
        self._url = "https://api.anthropic.com/v1/messages"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def cost_per_1k_input(self) -> float:
        return 0.00025

    @property
    def cost_per_1k_output(self) -> float:
        return 0.00125

    async def complete(self, prompt: str, system: str = "") -> AIResponse:
        headers = {
            "x-api-key": self._key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 150,
            "temperature": 0.1,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self._url, headers=headers, json=payload)
        elapsed = int((time.monotonic() - start) * 1000)

        if resp.status_code != 200:
            return AIResponse(content="", model=self._model, latency_ms=elapsed)

        data: dict[str, Any] = resp.json()
        content_blocks = data.get("content", [])
        content = ""
        if content_blocks and isinstance(content_blocks[0], dict):
            content = str(content_blocks[0].get("text", ""))
        usage = data.get("usage", {})

        tokens_in = int(usage.get("input_tokens", 0))
        tokens_out = int(usage.get("output_tokens", 0))

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
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": self._key, "anthropic-version": "2023-06-01"},
                )
            return resp.status_code == 200
        except Exception:
            return False
