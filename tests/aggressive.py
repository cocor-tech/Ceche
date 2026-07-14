"""Aggressive integration and edge-case tests for Ceche."""

from __future__ import annotations

import asyncio
import sys

from ceche.domain.models import TrademarkResult
from ceche.engine import AppraisalEngine


class _FakeRDAP:
    def __init__(self, registered: bool = True, created: str = "2000-01-01T00:00:00Z"):
        self._registered = registered
        self._created = created

    async def lookup(self, domain: str) -> dict:
        if self._registered:
            return {
                "ldhName": domain,
                "events": [
                    {"eventAction": "registration", "eventDate": self._created},
                    {"eventAction": "expiration", "eventDate": "2030-01-01T00:00:00Z"},
                ],
                "entities": [],
            }
        return {"_not_found": True}

    async def get(self, key: str) -> dict | None:
        return None

    async def set(self, key: str, value: dict, ttl: int) -> None:
        pass

    async def get_or_compute(self, key: str, ttl: int, fn):
        return await fn()


class _FakeCache:
    async def get(self, key: str) -> dict | None:
        return None

    async def set(self, key: str, value: dict, ttl: int) -> None:
        pass

    async def get_or_compute(self, key: str, ttl: int, fn):
        return await fn()


class _FakeKeyword:
    async def get_popularity(self, term: str) -> float:
        _map = {
            "car": 80, "insurance": 60, "top": 70,
            "go": 55, "daddy": 20, "best": 50,
            "business": 85, "money": 75, "loans": 90,
            "hospital": 45, "med": 30, "web": 40,
        }
        return float(_map.get(term, 0.0))


class _FakeTrademark:
    async def check(self, term: str) -> TrademarkResult:
        marks: dict[str, tuple[bool, str, list[str]]] = {
            "google": (True, "exact", ["Google"]),
            "godaddy": (True, "exact", ["GoDaddy"]),
            "facebook": (True, "exact", ["Facebook"]),
            "apple": (True, "exact", ["Apple"]),
            "amazon": (True, "exact", ["Amazon"]),
        }
        if term in marks:
            c, s, m = marks[term]
            return TrademarkResult(conflict=c, severity=s, marks=m)
        return TrademarkResult(conflict=False, severity="none", marks=[])


class _FakeWayback:
    async def get_snapshots(self, domain: str) -> dict:
        return {"count": 500, "first_date": "2010-01-01"}


class _FakeAhrefs:
    async def lookup(self, domain: str) -> float | None:
        return 45.0


class _FakeOPR:
    async def lookup(self, domain: str) -> dict:
        return {"rank": 50000, "score": 6.5, "ref_domains": 1200}


class _LoggingKeyword:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._real = _FakeKeyword()

    async def get_popularity(self, term: str) -> float:
        self.calls.append(term)
        return await self._real.get_popularity(term)


def _engine(registered: bool = True) -> AppraisalEngine:
    return AppraisalEngine(
        rdap=_FakeRDAP(registered=registered),  # type: ignore[arg-type]
        cache=_FakeCache(),  # type: ignore[arg-type]
        keyword=_FakeKeyword(),  # type: ignore[arg-type]
        trademark=_FakeTrademark(),  # type: ignore[arg-type]
        wayback=_FakeWayback(),  # type: ignore[arg-type]
        ahrefs=_FakeAhrefs(),  # type: ignore[arg-type]
        opr=_FakeOPR(),  # type: ignore[arg-type]
    )


async def main() -> int:
    failures = 0

    # ----------------------------------------------------------------
    # 1. DOMAIN PARSING EDGE CASES
    # ----------------------------------------------------------------
    print("\n=== 1. Domain parsing ===")
    engine = _engine()

    tests = [
        ("abc.com", "abc.com"),
        ("AbC.CoM", "abc.com"),
        ("TOPINSURANCE.CO", "topinsurance.co"),
        ("subdomain.example.com", "subdomain.example.com"),
    ]
    for input_domain, expected in tests:
        result = await engine.appraise(input_domain)
        if result.domain != expected:
            print(f"  FAIL parsing: {input_domain} -> {result.domain} (expected {expected})")
            failures += 1
        else:
            print(f"  OK   {input_domain} -> {result.domain}")

    # ----------------------------------------------------------------
    # 2. TLD TIER COVERAGE
    # ----------------------------------------------------------------
    print("\n=== 2. TLD tier coverage ===")
    tld_tests = [
        ("test.com", "tier_10", 100.0),
        ("test.net", "tier_09", 50.0),
        ("test.io", "tier_085", 50.0),
        ("test.co", "tier_08", 50.0),
        ("test.xyz", "tier_075", 30.0),
        ("test.icu", "tier_01", 5.0),
        ("test.nonexistent", "tier_00", 2.0),
    ]
    for domain, expected_tier, expected_base in tld_tests:
        result = await engine.appraise(domain)
        actual_tier = result.weight_profile
        if actual_tier != expected_tier:
            print(f"  FAIL tier: {domain} -> {actual_tier} (expected {expected_tier})")
            failures += 1
        else:
            print(f"  OK   {domain} -> {actual_tier} base ${expected_base}")

    # ----------------------------------------------------------------
    # 3. REGISTERED vs UNREGISTERED
    # ----------------------------------------------------------------
    print("\n=== 3. Registered vs unregistered ===")
    eng_reg = _engine(registered=True)
    eng_unreg = _engine(registered=False)

    r_reg = await eng_reg.appraise("example.com")
    r_unreg = await eng_unreg.appraise("example.com")

    if r_reg.estimated_value and r_unreg.estimated_value:
        if r_reg.estimated_value <= r_unreg.estimated_value:
            print(f"  FAIL registered({r_reg.estimated_value}) <= unregistered({r_unreg.estimated_value})")
            failures += 1
        else:
            print(f"  OK   registered ${r_reg.estimated_value:,.0f} > unregistered ${r_unreg.estimated_value:,.0f}")
    else:
        print(f"  OK   both produced values (or both None)")

    # ----------------------------------------------------------------
    # 4. TRADEMARK DOMAINS
    # ----------------------------------------------------------------
    print("\n=== 4. Trademark domains ===")
    tm_domains = {
        "google.com": True,
        "godaddy.io": True,
        "car.com": False,
        "fjfbfj.com": False,
    }
    for domain, expect_tm in tm_domains.items():
        result = await engine.appraise(domain)
        m11 = result.modules.get("m11_trademark", {})
        severity = m11.get("severity", "none")
        has_tm = severity in ("exact", "partial")
        if has_tm != expect_tm:
            print(f"  FAIL TM: {domain} -> severity={severity} (expected_has_tm={expect_tm})")
            failures += 1
        else:
            print(f"  OK   {domain} -> severity={severity}")

    # ----------------------------------------------------------------
    # 5. WORD COUNT SCENARIOS
    # ----------------------------------------------------------------
    print("\n=== 5. Word count scenarios ===")
    wc_tests = [
        # domain, expected_min_val (weak assertion — just must not crash)
        ("car.com", True),
        ("topinsurance.com", True),
        ("sadmecry.com", True),
        ("bestcarinsurancebroker.com", True),
    ]
    for domain, should_work in wc_tests:
        result = await engine.appraise(domain)
        if should_work and result.estimated_value is None:
            print(f"  FAIL {domain}: no value produced")
            failures += 1
        else:
            print(f"  OK   {domain} -> ${result.estimated_value:,.0f}" if result.estimated_value else f"  OK   {domain} -> None")

    # ----------------------------------------------------------------
    # 6. BRANDABLE FALLBACK
    # ----------------------------------------------------------------
    print("\n=== 6. Brandable fallback ===")
    brandable = ["fjfbfj", "zzzxxx"]
    for sld in brandable:
        domain = f"{sld}.com"
        result = await engine.appraise(domain)
        m6 = result.modules.get("m6_segmenter", {})
        m6_status = m6.get("status", "")
        has_m16 = "m16_brandability" in result.modules
        if m6_status == "no_split" and not has_m16:
            print(f"  FAIL {domain}: no_split but M16 not called")
            failures += 1
        else:
            print(f"  OK   {domain} -> M6={m6_status} M16_active={has_m16} val=${result.estimated_value:,.0f}" if result.estimated_value else f"  OK   {domain} -> M6={m6_status} M16_active={has_m16} val=None")

    # ----------------------------------------------------------------
    # 7. VALUE RANGES — SMOKE TEST
    # ----------------------------------------------------------------
    print("\n=== 7. Value range sanity ===")
    range_tests = [
        ("car.com", 500_000, 50_000_000),
        ("sadmecry.com", 1, 100_000),
        ("nekwasa.com", 1, 50_000),
        ("fjfbfj.com", 0, 1_000),  # should be near-zero
        ("google.com", 1, 500_000),  # trademark penalty
        ("godaddy.icu", 1, 1_000),  # trademark + weak TLD
        ("test.nonexistent", 0, 1_000),
    ]
    for domain, low, high in range_tests:
        result = await engine.appraise(domain)
        val = result.estimated_value or 0
        if not (low <= val <= high):
            print(f"  FAIL {domain}: ${val:,.0f} not in [{low:,.0f}, {high:,.0f}]")
            failures += 1
        else:
            print(f"  OK   {domain}: ${val:,.0f} in [{low:,.0f}, {high:,.0f}]")

    # ----------------------------------------------------------------
    # 8. PARALLEL EXECUTION — M7 gets correct words
    # ----------------------------------------------------------------
    print("\n=== 8. Parallel execution — M7 keyword calls ===")
    kw_logger = _LoggingKeyword()
    eng_kw = AppraisalEngine(
        rdap=_FakeRDAP(),  # type: ignore[arg-type]
        cache=_FakeCache(),  # type: ignore[arg-type]
        keyword=kw_logger,  # type: ignore[arg-type]
        trademark=_FakeTrademark(),  # type: ignore[arg-type]
        wayback=_FakeWayback(),  # type: ignore[arg-type]
        ahrefs=_FakeAhrefs(),  # type: ignore[arg-type]
        opr=_FakeOPR(),  # type: ignore[arg-type]
    )
    await eng_kw.appraise("topinsurance.com")
    if "top" not in kw_logger.calls or "insurance" not in kw_logger.calls:
        print(f"  FAIL M7 calls: {kw_logger.calls} — missing words")
        failures += 1
    else:
        print(f"  OK   M7 called with: {kw_logger.calls}")

    # ----------------------------------------------------------------
    # 9. CACHE INTEGRITY
    # ----------------------------------------------------------------
    print("\n=== 9. Cache integrity ===")
    import os
    import tempfile

    from ceche.infrastructure.cache.sqlite_adapter import SQLiteCacheAdapter
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(os.path.join(tmp, "cache.db"))
        cache = SQLiteCacheAdapter(db_path)
        await cache.set("test:key", {"x": 42}, 3600)
        v = await cache.get("test:key")
        if v != {"x": 42}:
            print(f"  FAIL cache get: {v}")
            failures += 1

        await cache.set("test:expired", {"x": 1}, -1)
        v2 = await cache.get("test:expired")
        if v2 is not None:
            print(f"  FAIL cache expired: {v2}")
            failures += 1

        # Multi-key persistence
        cache2 = SQLiteCacheAdapter(db_path)
        v3 = await cache2.get("test:key")
        if v3 != {"x": 42}:
            print(f"  FAIL cache persistence: {v3}")
            failures += 1
        else:
            print("  OK   cache set/get/expire/persist works")

    # ----------------------------------------------------------------
    # 10. MODULE STATUSES
    # ----------------------------------------------------------------
    print("\n=== 10. Module status tracking ===")
    result = await engine.appraise("car.com")
    mods = result.modules
    statuses = {k: v.get("status", "?") for k, v in mods.items()}
    expected_modules = {"m1_rdap", "m2_tld_table", "m3_length", "m4_word_count",
                        "m5_pronounceability", "m6_segmenter", "m7_keyword_popularity",
                        "m8_cpc", "m10_cross_tld", "m11_trademark", "m12_authority",
                        "m13_confidence", "m15_pricing"}
    missing = expected_modules - set(mods.keys())
    if missing:
        print(f"  FAIL missing module results: {missing}")
        failures += 1
    else:
        print(f"  OK   all {len(expected_modules)} expected modules present")

    # ----------------------------------------------------------------
    # 11. CONFIDENCE RATIO
    # ----------------------------------------------------------------
    print("\n=== 11. Confidence ratios ===")
    for domain, expect_high_conf in [("car.com", True), ("fjfbfj.com", False)]:
        result = await engine.appraise(domain)
        cr = result.completeness_ratio or 0
        if expect_high_conf and cr < 0.9:
            print(f"  FAIL {domain}: completeness={cr:.2f} (expected high)")
            failures += 1
        elif not expect_high_conf and cr > 0.9:
            print(f"  FAIL {domain}: completeness={cr:.2f} (expected lower)")
            failures += 1
        else:
            print(f"  OK   {domain}: completeness={cr:.2f}")

    # ----------------------------------------------------------------
    print(f"\n{'='*60}")
    if failures:
        print(f"  {failures} FAILURE(S) found!")
        return 1
    print("  ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
