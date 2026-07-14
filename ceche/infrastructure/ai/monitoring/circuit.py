from __future__ import annotations

import time
from typing import Any


class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300) -> None:
        self._threshold = failure_threshold
        self._recovery = recovery_timeout
        self._failures = 0
        self._last_failure = 0.0
        self._state = self.CLOSED

    @property
    def state(self) -> str:
        if self._state == self.OPEN and time.time() - self._last_failure > self._recovery:
            self._state = self.HALF_OPEN
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == self.OPEN

    def record_success(self) -> None:
        self._failures = 0
        self._state = self.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure = time.time()
        if self._failures >= self._threshold:
            self._state = self.OPEN

    def status(self) -> dict[str, Any]:
        return {
            "state": self._state,
            "failure_count": self._failures,
            "threshold": self._threshold,
            "last_failure": self._last_failure,
            "recovery_in": (
                max(0, self._recovery - int(time.time() - self._last_failure))
                if self._state == self.OPEN else 0
            ),
        }
