from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """Async token bucket rate limiter with burst support."""

    def __init__(self, rate: float, burst: int = 10) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        if burst < 1:
            raise ValueError("burst must be at least 1")
        self._rate = rate
        self._burst = float(burst)
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        async with self._lock:
            self._refill()
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0.0
                self._last_refill = time.monotonic()
            else:
                self._tokens -= 1.0

    def acquire_nowait(self) -> bool:
        """Try to consume a token without blocking. Returns True if consumed."""
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    @property
    def available(self) -> float:
        """Current token count (approximate, not under lock)."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        return min(self._burst, self._tokens + elapsed * self._rate)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now
