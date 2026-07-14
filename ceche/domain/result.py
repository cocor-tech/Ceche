from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppraisalResult:
    domain: str
    estimated_value: float | None
    range_low: float | None
    range_high: float | None
    confidence: str | None
    completeness_ratio: float | None
    tld_score: float | None
    weight_profile: str | None
    modules: dict[str, dict[str, Any]] = field(default_factory=dict)
