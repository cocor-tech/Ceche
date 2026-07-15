from __future__ import annotations

from typing import Any

import httpx

from ceche.infrastructure.rate.bucket import TokenBucket

_RATE_CFG: dict[str, float] = {
    "rdap": 5.0,
    "deepseek": 5.0,
    "kimi": 3.0,
    "glm": 3.0,
    "minimax": 3.0,
    "openai": 5.0,
    "google_cse": 10.0,
    "wayback": 5.0,
    "ahrefs": 1.0,
    "opr": 2.0,
    "brave": 5.0,
}

_BURST_CFG: dict[str, int] = {
    "rdap": 10,
    "deepseek": 15,
    "kimi": 10,
    "glm": 10,
    "minimax": 10,
    "openai": 15,
    "google_cse": 20,
    "wayback": 10,
    "ahrefs": 3,
    "opr": 5,
    "brave": 10,
}


class RateLimiter:
    """Per-provider rate limiter backed by TokenBucket instances."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def _ensure(self, provider: str) -> TokenBucket:
        if provider not in self._buckets:
            rate = _RATE_CFG.get(provider, 5.0)
            burst = _BURST_CFG.get(provider, 10)
            self._buckets[provider] = TokenBucket(rate=rate, burst=burst)
        return self._buckets[provider]

    async def acquire(self, provider: str) -> None:
        bucket = self._ensure(provider)
        await bucket.acquire()

    def client_for(self, provider: str, **kwargs: Any) -> httpx.AsyncClient:
        transport = RateLimitedTransport(
            transport=httpx.AsyncHTTPTransport(),
            limiter=self,
            provider=provider,
        )
        return httpx.AsyncClient(transport=transport, **kwargs)


class RateLimitedTransport(httpx.AsyncBaseTransport):
    """httpx transport wrapper that rate-limits all requests."""

    def __init__(
        self,
        transport: httpx.AsyncBaseTransport,
        limiter: RateLimiter,
        provider: str,
    ) -> None:
        self._transport = transport
        self._limiter = limiter
        self._provider = provider

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await self._limiter.acquire(self._provider)
        return await self._transport.handle_async_request(request)
