from __future__ import annotations

import asyncio
import datetime
import importlib.metadata
from collections.abc import Sequence
from typing import Any, ClassVar

from ceche.domain.models import ModuleStatus
from ceche.domain.modules.m01_rdap import M1RDAP
from ceche.domain.modules.m02_tld_table import M2TLDTable
from ceche.domain.modules.m03_length import M3Length
from ceche.domain.modules.m04_word_count import M4WordCount
from ceche.domain.modules.m05_pronounceability import M5Pronounceability
from ceche.domain.modules.m06_segmenter import M6Segmenter
from ceche.domain.modules.m07_keyword_popularity import M7KeywordPopularity
from ceche.domain.modules.m08_cpc import M8CPC
from ceche.domain.modules.m09_search_results import M9SearchResults
from ceche.domain.modules.m10_cross_tld import M10CrossTLD
from ceche.domain.modules.m11_trademark import M11Trademark
from ceche.domain.modules.m12_authority import M12Authority
from ceche.domain.modules.m13_confidence import M13Confidence
from ceche.domain.modules.m15_pricing import M15Pricing
from ceche.domain.modules.m16_brandability import M16Brandability
from ceche.domain.ports import (
    AIPort,
    CachePort,
    KeywordPopularityPort,
    RDAPPort,
    SearchPort,
    TrademarkPort,
)
from ceche.domain.result import AppraisalResult
from ceche.infrastructure.ai.router import ModelRouter
from ceche.infrastructure.authority.ahrefs_adapter import AhrefsDRAdapter
from ceche.infrastructure.authority.opr_adapter import OPRAdapter
from ceche.infrastructure.authority.wayback_adapter import WaybackAdapter


class _ModuleAIPort(AIPort):
    def __init__(self, router: ModelRouter, module_name: str) -> None:
        self._router = router
        self._name = module_name

    async def complete(self, prompt: str) -> str:
        return await self._router.complete(self._name, prompt)


def _get(ctx: dict[str, Any], key: str, field: str = "") -> Any:
    val = ctx.get(key)
    if isinstance(val, dict) and field:
        return val.get(field)
    return val


class AppraisalEngine:
    def __init__(
        self,
        rdap: RDAPPort,
        cache: CachePort,
        keyword: KeywordPopularityPort | None = None,
        search: SearchPort | None = None,
        search_backup: SearchPort | None = None,
        trademark: TrademarkPort | None = None,
        trademark_backup: TrademarkPort | None = None,
        wayback: WaybackAdapter | None = None,
        ahrefs: AhrefsDRAdapter | None = None,
        opr: OPRAdapter | None = None,
        router: ModelRouter | None = None,
    ) -> None:
        ai_m6 = _ModuleAIPort(router, "m6") if router else None
        ai_m8 = _ModuleAIPort(router, "m8") if router else None
        ai_m11 = _ModuleAIPort(router, "m11") if router else None
        ai_m16 = _ModuleAIPort(router, "m16") if router else None

        self._m1 = M1RDAP(rdap, cache)
        self._m2 = M2TLDTable()
        self._m3 = M3Length()
        self._m4 = M4WordCount()
        self._m5 = M5Pronounceability()
        self._m6 = M6Segmenter(ai_m6)
        self._m7 = M7KeywordPopularity(keyword) if keyword else None
        self._m8 = M8CPC(ai=ai_m8)
        self._m9: M9SearchResults | None
        if search:
            self._m9 = M9SearchResults(search, search_backup)
        elif search_backup:
            self._m9 = M9SearchResults(search_backup, None)
        else:
            self._m9 = None
        self._m10 = M10CrossTLD(rdap)
        self._m11 = M11Trademark(trademark, trademark_backup, ai=ai_m11) if trademark else None
        self._m12 = (
            M12Authority(wayback=wayback, ahrefs=ahrefs, opr=opr)
            if wayback else None
        )
        self._m13 = M13Confidence()
        self._m15 = M15Pricing()
        self._m16 = M16Brandability(ai=ai_m16)

    async def appraise(self, domain: str, fresh: bool = False) -> AppraisalResult:
        ctx: dict[str, Any] = {}
        if fresh:
            ctx["_fresh"] = True

        import re as _re
        cleaned = domain.strip().lower()
        if not _re.match(r'^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)*\.[a-z]{2,}$', cleaned):
            raise ValueError(f"Invalid domain: '{domain}' — must be a valid domain name (e.g. example.com)")

        parts = cleaned.rsplit(".", 1)
        sld = parts[0] if len(parts) == 2 else cleaned
        tld = parts[1] if len(parts) == 2 else ""

        ctx["domain_name"] = cleaned
        ctx["sld"] = sld
        ctx["tld"] = tld.lower().lstrip(".")
        domain_normalized = ctx["domain_name"]

        # Phase 1
        results = await asyncio.gather(
            self._m1.run(ctx),
            self._m2.run(ctx),
            self._m6.run(ctx),
            return_exceptions=True,
        )
        self._ingest(ctx, results, ["m1_rdap", "m2_tld_table", "m6_segmenter"])

        ctx["registered"] = _get(ctx, "result_m1_rdap", "registered") is not False
        ctx["age_years"] = _get(ctx, "result_m1_rdap", "age_years")
        ctx["words"] = _get(ctx, "result_m6_segmenter", "winner")
        ctx["word_count"] = _get(ctx, "result_m6_segmenter", "word_count")
        ctx["m6_status"] = _get(ctx, "result_m6_segmenter", "status")
        ctx["weight_profile"] = _get(ctx, "result_m2_tld_table", "weight_profile")

        # Phase 2
        r3 = await self._safe(self._m3.run(ctx))
        r4 = await self._safe(self._m4.run(ctx))
        r5 = await self._safe(self._m5.run(ctx))
        self._ingest_single(ctx, r3, "m3_length")
        self._ingest_single(ctx, r4, "m4_word_count")
        self._ingest_single(ctx, r5, "m5_pronounceability")

        is_no_split = ctx.get("m6_status") == "no_split"

        if not is_no_split:
            tasks = []
            names = []
            if self._m7:
                tasks.append(self._m7.run(ctx))
                names.append("m7_keyword_popularity")
            tasks.append(self._m8.run(ctx))
            names.append("m8_cpc")
            if self._m11:
                tasks.append(self._m11.run(ctx))
                names.append("m11_trademark")
            results_3 = await asyncio.gather(*tasks, return_exceptions=True)
            self._ingest(ctx, results_3, names)

        # Phase 4
        p4_tasks = []
        p4_names = []
        if self._m9:
            p4_tasks.append(self._m9.run(ctx))
            p4_names.append("m9_search_results")
        p4_tasks.append(self._m10.run(ctx))
        p4_names.append("m10_cross_tld")
        if self._m12 and ctx.get("registered"):
            p4_tasks.append(self._m12.run(ctx))
            p4_names.append("m12_authority")
        if p4_tasks:
            results_4 = await asyncio.gather(*p4_tasks, return_exceptions=True)
            self._ingest(ctx, results_4, p4_names)

        # Phase 5 — brandable
        if is_no_split:
            tasks = []
            names = []
            if self._m8:
                tasks.append(self._m8.run(ctx))
                names.append("m8_cpc")
            if self._m7:
                tasks.append(self._m7.run(ctx))
                names.append("m7_keyword_popularity")
            if tasks:
                results_b = await asyncio.gather(*tasks, return_exceptions=True)
                self._ingest(ctx, results_b, names)
            r16 = await self._safe(self._m16.run(ctx))
            self._ingest_single(ctx, r16, "m16_brandability")

        # Phase 6
        r13 = await self._safe(self._m13.run(ctx))
        self._ingest_single(ctx, r13, "m13_confidence")
        ctx["completeness_ratio"] = (
            r13.data.get("completeness_ratio") if r13 and r13.data else 0.0
        )

        r15 = await self._safe(self._m15.run(ctx))
        self._ingest_single(ctx, r15, "m15_pricing")

        pricing = r15.data if r15 else {}
        estimated = pricing.get("estimated_value")
        prange = pricing.get("range", {})
        range_low = prange.get("low") if isinstance(prange, dict) else None
        range_high = prange.get("high") if isinstance(prange, dict) else None

        return AppraisalResult(
            domain=domain_normalized,
            estimated_value=float(estimated) if estimated else None,
            range_low=float(range_low) if range_low else None,
            range_high=float(range_high) if range_high else None,
            confidence=r13.data.get("label") if r13 and r13.data else None,
            completeness_ratio=ctx.get("completeness_ratio"),
            tld_score=_get(ctx, "result_m2_tld_table", "tld_score"),
            weight_profile=ctx.get("weight_profile"),
            modules=self._module_breakdown(ctx),
            version=importlib.metadata.version("ceche"),
            generated_at=datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
        )

    def _ingest_single(self, ctx: dict[str, Any], result: Any, name: str) -> None:
        if result is None or isinstance(result, BaseException):
            return
        data = getattr(result, "data", {}) or {}
        value = getattr(result, "value", None)
        module_status = getattr(result, "status", ModuleStatus.SKIPPED)
        entry = dict(data) if isinstance(data, dict) else {}
        entry.setdefault("_module_status", str(module_status))
        ctx[f"result_{name}"] = entry
        if value is not None:
            ctx[f"mult_{name}"] = value

    def _ingest(
        self,
        ctx: dict[str, Any],
        results: Sequence[Any],
        names: list[str],
    ) -> None:
        for name, result in zip(names, results, strict=False):
            self._ingest_single(ctx, result, name)

    @staticmethod
    async def _safe(coro: Any) -> Any:
        try:
            return await coro
        except Exception:
            import sys as _sys
            import traceback as _tb
            _sys.stderr.write(f"[engine] module error: {_tb.format_exc()}\n")
            _sys.stderr.flush()
            return None

    _MODULE_NAMES: ClassVar[list[str]] = [
        "m1_rdap", "m2_tld_table", "m3_length", "m4_word_count",
        "m5_pronounceability", "m6_segmenter", "m7_keyword_popularity",
        "m8_cpc", "m9_search_results", "m10_cross_tld",
        "m11_trademark", "m12_authority", "m13_confidence",
        "m15_pricing", "m16_brandability",
    ]

    def _module_exists(self, name: str) -> bool:
        mapping: dict[str, bool] = {
            "m1_rdap": True,
            "m2_tld_table": True,
            "m3_length": True,
            "m4_word_count": True,
            "m5_pronounceability": True,
            "m6_segmenter": True,
            "m7_keyword_popularity": self._m7 is not None,
            "m8_cpc": True,
            "m9_search_results": self._m9 is not None,
            "m10_cross_tld": True,
            "m11_trademark": self._m11 is not None,
            "m12_authority": self._m12 is not None,
            "m13_confidence": True,
            "m15_pricing": True,
            "m16_brandability": True,
        }
        return mapping.get(name, False)

    def _skip_reason(self, name: str, ctx: dict[str, Any]) -> str:
        m6_status: str | None = ctx.get("m6_status")
        registered: bool = ctx.get("registered", True)
        reasons: dict[str, str] = {
            "m16_brandability": (
                "M6 found a split \u2014 brandability not applicable"
                if m6_status == "split_found"
                else "Not applicable for this domain"
            ),
            "m7_keyword_popularity": (
                "Brandable domain \u2014 keyword analysis not applicable"
                if m6_status == "no_split"
                else "Not applicable for this domain"
            ),
            "m8_cpc": (
                "Brandable domain \u2014 CPC analysis not applicable"
                if m6_status == "no_split"
                else "Not applicable for this domain"
            ),
            "m9_search_results": "No search adapter configured",
            "m11_trademark": (
                "Brandable domain \u2014 trademark check not applicable"
                if m6_status == "no_split"
                else "Not applicable for this domain"
            ),
            "m12_authority": (
                "Domain not registered"
                if not registered
                else "Not applicable for this domain"
            ),
        }
        return reasons.get(name, "Not applicable for this domain type")

    def _module_breakdown(
        self,
        ctx: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        breakdown: dict[str, dict[str, Any]] = {}
        for name in self._MODULE_NAMES:
            raw = ctx.get(f"result_{name}")
            if raw is None or not isinstance(raw, dict):
                if self._module_exists(name):
                    breakdown[name] = {
                        "status": "SKIPPED",
                        "reason": self._skip_reason(name, ctx),
                    }
                else:
                    breakdown[name] = {
                        "status": "UNAVAILABLE",
                        "reason": "No adapter configured",
                    }
                continue
            entry = dict(raw)
            ms = entry.pop("_module_status", "")
            if name == "m6_segmenter" and "status" in entry:
                entry["result"] = entry.pop("status")
            entry["status"] = ms.replace("ModuleStatus.", "") if ms else ""
            breakdown[name] = entry
        return breakdown
