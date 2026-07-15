from __future__ import annotations

import asyncio
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass

from ceche.domain.result import AppraisalResult
from ceche.engine import AppraisalEngine


@dataclass
class BulkFailure:
    domain: str
    error_type: str
    error_message: str
    phase: str | None = None
    traceback_text: str | None = None


@dataclass
class BulkSummary:
    total: int
    succeeded: int
    failed: int
    duration_seconds: float
    rate_domains_per_second: float


@dataclass
class BulkReport:
    summary: BulkSummary
    results: list[AppraisalResult]
    failures: list[BulkFailure]


class BulkAppraisalEngine:
    def __init__(
        self,
        engine: AppraisalEngine,
        concurrency: int = 10,
        fresh: bool = False,
    ) -> None:
        self._engine = engine
        self._sem = asyncio.Semaphore(max(1, concurrency))
        self._fresh = fresh

    async def run(
        self,
        domains: list[str],
        on_progress: Callable[[int, int, int], None] | None = None,
    ) -> BulkReport:
        """Process all domains concurrently with failure isolation.

        Args:
            domains: List of domain names to appraise.
            on_progress: Called as (total, succeeded, failed) after each domain
                         completes or fails. May be called from any concurrent task.

        Returns:
            BulkReport with results, failures, and summary.
        """
        results: list[AppraisalResult] = []
        failures: list[BulkFailure] = []
        total = len(domains)
        lock = asyncio.Lock()

        start = time.monotonic()

        async def _one(domain: str) -> None:
            async with self._sem:
                try:
                    result = await self._engine.appraise(domain, fresh=self._fresh)
                except Exception as exc:
                    async with lock:
                        failures.append(BulkFailure(
                            domain=domain,
                            error_type=type(exc).__name__,
                            error_message=str(exc) or "(no message)",
                            traceback_text=traceback.format_exc(),
                        ))
                        if on_progress:
                            on_progress(total, len(results), len(failures))
                    return

                async with lock:
                    results.append(result)
                    if on_progress:
                        on_progress(total, len(results), len(failures))

        tasks = [_one(d) for d in domains]
        await asyncio.gather(*tasks)

        duration = time.monotonic() - start
        succeeded = len(results)
        rate = succeeded / duration if duration > 0 and succeeded > 0 else 0.0

        return BulkReport(
            summary=BulkSummary(
                total=total,
                succeeded=succeeded,
                failed=len(failures),
                duration_seconds=round(duration, 2),
                rate_domains_per_second=round(rate, 2),
            ),
            results=results,
            failures=failures,
        )

    # _appraise_one removed — folding into inline closure above
