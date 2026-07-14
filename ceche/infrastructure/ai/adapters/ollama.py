from __future__ import annotations

import time
from typing import Any

import httpx

from ceche.infrastructure.ai.adapters.base import AIResponse, BaseAIAdapter


class OllamaAdapter(BaseAIAdapter):
    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434") -> None:
        self._model = model
        self._url = f"{base_url}/api/chat"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def cost_per_1k_input(self) -> float:
        return 0.0

    @property
    def cost_per_1k_output(self) -> float:
        return 0.0

    async def complete(self, prompt: str, system: str = "") -> AIResponse:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 150},
        }

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(self._url, json=payload)
        except Exception:
            return AIResponse(content="", model=self._model, latency_ms=0)

        elapsed = int((time.monotonic() - start) * 1000)

        if resp.status_code != 200:
            return AIResponse(content="", model=self._model, latency_ms=elapsed)

        data: dict[str, Any] = resp.json()
        content = str(data.get("message", {}).get("content", ""))
        tokens_in = int(data.get("prompt_eval_count", 0))
        tokens_out = int(data.get("eval_count", 0))

        return AIResponse(
            content=content,
            model=self._model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=0.0,
            latency_ms=elapsed,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._url.rsplit('/', 1)[0]}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False
