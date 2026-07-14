from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule
from ceche.infrastructure.authority.ahrefs_adapter import AhrefsDRAdapter
from ceche.infrastructure.authority.opr_adapter import OPRAdapter
from ceche.infrastructure.authority.wayback_adapter import WaybackAdapter


class M12Authority(BaseModule):
    name = "m12_authority"

    def __init__(
        self,
        wayback: WaybackAdapter,
        ahrefs: AhrefsDRAdapter | None = None,
        opr: OPRAdapter | None = None,
    ) -> None:
        self._wayback = wayback
        self._ahrefs = ahrefs
        self._opr = opr

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        domain: str | None = context.get("domain_name")
        if not domain:
            return ModuleResult.error(self.name, "no domain_name in context")

        registered: bool | None = context.get("registered")
        age_years: float | None = context.get("age_years")

        if not registered:
            return ModuleResult(
                module_name=self.name,
                value=None,
                confidence=0.0,
                data={"reason": "unregistered domain"},
                status=ModuleStatus.SKIPPED,
            )

        wayback_data = await self._wayback.get_snapshots(domain)
        snapshots = _to_int(wayback_data.get("count", 0))
        parked = WaybackAdapter.parked_flag(snapshots, age_years)

        ahrefs_dr: float | None = None
        if self._ahrefs is not None:
            try:
                ahrefs_dr = await self._ahrefs.lookup(domain)
            except Exception:
                ahrefs_dr = None

        opr_raw: dict[str, Any] = {}
        opr_score: float | None = None
        if self._opr is not None:
            try:
                opr_raw = await self._opr.lookup(domain)
                raw_score = opr_raw.get("score")
                if isinstance(raw_score, (int, float)):
                    opr_score = float(raw_score)
            except Exception:
                opr_score = None

        if parked and _has_authority_signals(ahrefs_dr, opr_score):
            parked = False

        authority = _dynamic_blend(ahrefs_dr, opr_score, snapshots)
        multiplier = _authority_multiplier(authority, parked)
        if context.get("is_canonical_brand"):
            multiplier = min(multiplier, 3.0)
        sources_active = _count_sources(ahrefs_dr, opr_score)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=_confidence_from_sources(sources_active),
            data={
                "age_years": age_years,
                "snapshots": snapshots,
                "parked": parked,
                "ahrefs_dr": ahrefs_dr,
                "opr_score": opr_score,
                "authority": round(authority, 3) if authority is not None else None,
                "multiplier": multiplier,
                "sources_active": sources_active,
                "sources_total": _total_available(self._ahrefs, self._opr),
            },
            status=ModuleStatus.SUCCESS,
        )


def _has_authority_signals(ahrefs: float | None, opr: float | None) -> bool:
    return bool((ahrefs is not None and ahrefs > 0) or (opr is not None and opr > 0))


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _snapshot_score(snapshots: int) -> float:
    if snapshots >= 1000:
        return 1.0
    if snapshots >= 100:
        return 0.7
    if snapshots >= 10:
        return 0.4
    if snapshots > 0:
        return 0.2
    return 0.0


def _dynamic_blend(
    ahrefs: float | None,
    opr: float | None,
    snapshots: int,
) -> float | None:
    scores: list[float] = []
    weights: list[float] = []

    if ahrefs is not None:
        scores.append(ahrefs / 100.0)
        weights.append(1.0)

    if opr is not None:
        scores.append(opr / 10.0)
        weights.append(0.8)

    hist = _snapshot_score(snapshots)
    scores.append(hist)
    weights.append(0.1)

    if not scores:
        return None

    total_weight = sum(weights)
    return sum(s * w for s, w in zip(scores, weights, strict=False)) / total_weight


def _count_sources(ahrefs: float | None, opr: float | None) -> int:
    count = 1
    if ahrefs is not None:
        count += 1
    if opr is not None:
        count += 1
    return count


def _total_available(ahrefs: object, opr: object) -> int:
    total = 1
    if ahrefs is not None:
        total += 1
    if opr is not None:
        total += 1
    return total


def _confidence_from_sources(sources_active: int) -> float:
    if sources_active >= 3:
        return 1.0
    if sources_active == 2:
        return 0.7
    return 0.4


def _authority_multiplier(authority: float | None, parked: bool) -> float:
    if parked:
        return 0.5
    if authority is None:
        return 1.0
    if authority >= 0.90:
        return 48.0
    if authority >= 0.80:
        return 15.0
    if authority >= 0.70:
        return 8.0
    if authority >= 0.60:
        return 5.0
    if authority >= 0.45:
        return 3.0
    if authority >= 0.20:
        return 1.2
    return 1.0
