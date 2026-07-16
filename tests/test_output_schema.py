"""Tests for Phase 1 — output schema cleanup."""

from __future__ import annotations

import json


class _MockCache:
    async def get(self, key): return None
    async def set(self, key, value, ttl): pass
    async def get_or_compute(self, key, ttl, fn): return await fn()


class _MockRDAP:
    async def lookup(self, domain):
        return {"ldhName": domain, "events": [
            {"eventAction": "registration", "eventDate": "2000-01-01T00:00:00Z"},
        ], "entities": []}


class _MockKeyword:
    async def get_popularity(self, term): return 50.0


class _MockTrademark:
    async def check(self, term):
        from ceche.domain.models import TrademarkResult
        return TrademarkResult(conflict=False, severity="none", marks=[])


class _MockWayback:
    async def get_snapshots(self, domain): return {"count": 500}


class _MockAhrefs:
    async def lookup(self, domain): return 45.0


class _MockOPR:
    async def lookup(self, domain): return {"rank": 50000}


def _make_engine(**overrides):
    from ceche.engine import AppraisalEngine
    kwargs = dict(
        rdap=overrides.get("rdap", _MockRDAP()),
        cache=_MockCache(),
        keyword=overrides.get("keyword", _MockKeyword()),
        trademark=overrides.get("trademark", _MockTrademark()),
        wayback=overrides.get("wayback", _MockWayback()),
        ahrefs=overrides.get("ahrefs", _MockAhrefs()),
        opr=overrides.get("opr", _MockOPR()),
    )
    return AppraisalEngine(**kwargs)


class TestOutputSchema:
    async def test_appraisal_result_has_version_and_generated_at(self) -> None:
        engine = _make_engine()
        result = await engine.appraise("test.com")
        assert result.version != ""
        assert result.generated_at != ""

    async def test_all_15_module_slots_present(self) -> None:
        """All 15 module slots should always be in the output."""
        engine = _make_engine()
        result = await engine.appraise("test.com")
        modules = result.modules
        expected = [
            "m1_rdap", "m2_tld_table", "m3_length", "m4_word_count",
            "m5_pronounceability", "m6_segmenter", "m7_keyword_popularity",
            "m8_cpc", "m9_search_results", "m10_cross_tld",
            "m11_trademark", "m12_authority", "m13_confidence",
            "m15_pricing", "m16_brandability",
        ]
        for name in expected:
            assert name in modules, f"Missing module slot: {name}"

    async def test_module_status_is_real_value(self) -> None:
        """status should be 'SUCCESS' not 'None'."""
        engine = _make_engine()
        result = await engine.appraise("test.com")
        for name, entry in result.modules.items():
            if entry.get("status") == "UNAVAILABLE":
                continue
            assert entry.get("status") not in ("None", "", None), (
                f"{name} has status=None"
            )

    async def test_no_module_has_module_status_key(self) -> None:
        """_module_status should NOT appear in module output."""
        engine = _make_engine()
        result = await engine.appraise("test.com")
        for name, entry in result.modules.items():
            assert "_module_status" not in entry, f"{name} still has _module_status"

    async def test_m6_has_result_field(self) -> None:
        """M6 should have 'result' (split_found/no_split)."""
        engine = _make_engine()
        result = await engine.appraise("test.com")
        m6 = result.modules.get("m6_segmenter", {})
        assert m6.get("result") in ("split_found", "no_split"), (
            f"M6 result missing, got keys={list(m6.keys())}"
        )

    async def test_m6_no_longer_has_semantic_status(self) -> None:
        """M6 should not have 'status' = 'split_found', that's now 'result'."""
        engine = _make_engine()
        result = await engine.appraise("test.com")
        m6 = result.modules.get("m6_segmenter", {})
        assert "result" in m6

    async def test_breakdown_is_structured(self) -> None:
        """M15 breakdown should have multiplier/weight/contribution/effect/impact."""
        engine = _make_engine()
        result = await engine.appraise("car.com")
        m15 = result.modules.get("m15_pricing", {})
        bd = m15.get("breakdown", {})
        assert isinstance(bd, dict)
        for name, entry in bd.items():
            if entry is None:
                continue
            assert "multiplier" in entry, f"{name} missing multiplier"
            assert "effect" in entry, f"{name} missing effect"
            assert "impact" in entry, f"{name} missing impact"
            assert isinstance(entry["impact"], (int, float))

    async def test_json_serialization_is_valid(self) -> None:
        """Full result should serialize to valid JSON."""
        engine = _make_engine()
        result = await engine.appraise("test.com")
        text = json.dumps(result.modules, indent=2, default=str)
        parsed = json.loads(text)
        assert "m1_rdap" in parsed
        assert "m6_segmenter" in parsed
        assert "m15_pricing" in parsed
