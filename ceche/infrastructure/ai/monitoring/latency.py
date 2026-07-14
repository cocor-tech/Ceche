from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LatencyRecord:
    count: int = 0
    values: list[int] = field(default_factory=list)

    def add(self, ms: int) -> None:
        self.count += 1
        self.values.append(ms)
        if len(self.values) > 1000:
            self.values = self.values[-1000:]

    def stats(self) -> dict[str, Any]:
        if not self.values:
            return {"count": 0, "avg_ms": 0, "max_ms": 0}
        sorted_vals = sorted(self.values)
        return {
            "count": self.count,
            "avg_ms": round(statistics.mean(self.values), 1),
            "p50_ms": sorted_vals[len(sorted_vals) // 2],
            "p95_ms": sorted_vals[int(len(sorted_vals) * 0.95)],
            "p99_ms": sorted_vals[int(len(sorted_vals) * 0.99)],
            "max_ms": max(self.values),
        }


class LatencyMonitor:
    def __init__(self) -> None:
        self._records: dict[str, LatencyRecord] = defaultdict(LatencyRecord)

    def record(self, module: str, latency_ms: int) -> None:
        self._records[module].add(latency_ms)

    def stats(self) -> dict[str, dict[str, Any]]:
        return {name: rec.stats() for name, rec in self._records.items()}

    def overall(self) -> dict[str, Any]:
        all_vals: list[int] = []
        for rec in self._records.values():
            all_vals.extend(rec.values)
        if not all_vals:
            return {"avg_ms": 0, "p95_ms": 0, "max_ms": 0}
        sorted_vals = sorted(all_vals)
        return {
            "avg_ms": round(statistics.mean(all_vals), 1),
            "p95_ms": sorted_vals[int(len(sorted_vals) * 0.95)],
            "max_ms": max(all_vals),
        }
