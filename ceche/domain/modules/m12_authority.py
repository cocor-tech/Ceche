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
        ahrefs: AhrefsDRAdapter,
        opr: OPRAdapter,
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

        ahrefs_dr = await self._ahrefs.lookup(domain)
        opr_data = await self._opr.lookup(domain)
        opr_score: float | None = opr_data.get("score")
        if isinstance(opr_score, (int, float)):
            opr_score = float(opr_score)

        authority = _blend_authority(ahrefs_dr, opr_score)

        multiplier = _authority_multiplier(authority, parked)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=_confidence(ahrefs_dr, opr_score),
            data={
                "age_years": age_years,
                "snapshots": snapshots,
                "parked": parked,
                "ahrefs_dr": ahrefs_dr,
                "opr_score": opr_score,
                "authority": round(authority, 2) if authority is not None else None,
                "multiplier": multiplier,
            },
            status=ModuleStatus.SUCCESS,
        )


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _blend_authority(ahrefs: float | None, opr: float | None) -> float | None:
    if ahrefs is not None and opr is not None:
        return ahrefs / 100 * 0.6 + opr / 10 * 0.4
    if ahrefs is not None:
        return ahrefs / 100 * 0.8
    if opr is not None:
        return opr / 10 * 0.8
    return None


def _authority_multiplier(authority: float | None, parked: bool) -> float:
    if authority is None:
        authority = 0.0
    if parked:
        return min(0.5, authority)
    if authority >= 0.90:
        return 3.0
    if authority >= 0.50:
        return 2.0
    if authority >= 0.20:
        return 1.2
    return 1.0


def _confidence(ahrefs: float | None, opr: float | None) -> float:
    sources = bool(ahrefs is not None) + bool(opr is not None)
    if sources >= 2:
        return 1.0
    if sources == 1:
        return 0.6
    return 0.0
