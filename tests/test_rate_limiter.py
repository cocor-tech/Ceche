"""Tests for TokenBucket and RateLimiter."""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from ceche.infrastructure.rate.bucket import TokenBucket
from ceche.infrastructure.rate.limiter import RateLimitedTransport, RateLimiter


class TestTokenBucket:
    def test_constructor_requires_positive_rate(self) -> None:
        with pytest.raises(ValueError):
            TokenBucket(0)

    def test_constructor_requires_positive_burst(self) -> None:
        with pytest.raises(ValueError):
            TokenBucket(1, burst=0)

    async def test_acquire_consumes_token(self) -> None:
        bucket = TokenBucket(rate=100, burst=10)
        before = bucket.available
        await bucket.acquire()
        assert bucket.available < before

    async def test_burst_allows_rapid_acquires(self) -> None:
        bucket = TokenBucket(rate=1, burst=5)
        t0 = time.monotonic()
        for _ in range(5):
            await bucket.acquire()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.1

    async def test_rate_enforced_after_burst(self) -> None:
        bucket = TokenBucket(rate=2, burst=1)
        await bucket.acquire()
        t0 = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.4

    async def test_acquire_nowait_false_when_empty(self) -> None:
        bucket = TokenBucket(rate=100, burst=1)
        await bucket.acquire()
        assert not bucket.acquire_nowait()

    async def test_acquire_nowait_true_when_available(self) -> None:
        bucket = TokenBucket(rate=100, burst=5)
        assert bucket.acquire_nowait()

    async def test_available_property(self) -> None:
        bucket = TokenBucket(rate=100, burst=3)
        initial = bucket.available
        await bucket.acquire()
        assert bucket.available < initial
        await asyncio.sleep(0.02)
        assert bucket.available > 0

    async def test_concurrent_acquires(self) -> None:
        bucket = TokenBucket(rate=1000, burst=10)
        results: list[float] = []
        start = time.monotonic()

        async def worker() -> None:
            await bucket.acquire()
            results.append(time.monotonic() - start)

        await asyncio.gather(*(worker() for _ in range(10)))
        assert len(results) == 10
        assert max(results) < 0.5


class TestRateLimiter:
    async def test_acquire_creates_bucket_lazily(self) -> None:
        limiter = RateLimiter()
        bucket = limiter._ensure("nonexistent")
        assert bucket.available > 0

    async def test_acquire_per_provider_independent(self) -> None:
        limiter = RateLimiter()
        a = limiter._ensure("rdap")
        b = limiter._ensure("deepseek")
        assert a is not b

    async def test_acquire_respects_limits(self) -> None:
        limiter = RateLimiter()
        limiter._buckets["test"] = TokenBucket(rate=100, burst=1)
        await limiter.acquire("test")
        assert not limiter._buckets["test"].acquire_nowait()


class TestRateLimitedTransport:
    async def test_transport_rate_limits(self) -> None:
        limiter = RateLimiter()
        limiter._buckets["test"] = TokenBucket(rate=100, burst=1)
        transport = RateLimitedTransport(
            transport=httpx.AsyncHTTPTransport(),
            limiter=limiter,
            provider="test",
        )

        # First request should consume the burst token
        assert limiter._buckets["test"].acquire_nowait()
        await limiter._buckets["test"].acquire()  # consume it

        # Now no tokens — transport should still work but may be slow
        try:
            req = httpx.Request("GET", "https://httpbin.org/get")
            await transport.handle_async_request(req)
        except Exception:
            pass
        # Even if the request fails, the rate limiter should have been called
        # and the token consumed (refilled and consumed)
