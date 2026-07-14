"""Tests for M15 — Pricing / Valuation Module."""

from __future__ import annotations

import pytest

from ceche.domain import M15Pricing, ModuleStatus


@pytest.fixture
def m15():
    return M15Pricing()


class TestM15Pricing:
    async def test_full_pipeline_com(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "mult_m1_rdap": 3.0,
            "mult_m3_length": 15.0,
            "mult_m4_word_count": 20.0,
            "mult_m5_pronounceability": 2.0,
            "mult_m7_keyword_popularity": 8.0,
            "mult_m8_cpc": 1.0,
            "mult_m9_search_results": 5.0,
            "mult_m10_cross_tld": 1.0,
            "mult_m11_trademark": 1.0,
            "mult_m12_authority": 3.0,
            "completeness_ratio": 1.0,
        }
        result = await m15.run(ctx)
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["estimated_value"] > 1000000

    async def test_brandable_unregistered(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "mult_m3_length": 2.0,
            "mult_m5_pronounceability": 1.5,
            "mult_m16_brandability": 5.0,
            "mult_m10_cross_tld": 1.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 0.5,
        }
        result = await m15.run(ctx)
        assert result.data["estimated_value"] > 500
        assert result.data["range"]["low"] < result.data["range"]["high"]

    async def test_trademark_conflict_drops_value(self, m15):
        ctx_good = {
            "weight_profile": "tier_10",
            "mult_m4_word_count": 20.0,
            "mult_m3_length": 15.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 1.0,
        }
        ctx_bad = {**ctx_good, "mult_m11_trademark": 0.1}

        r_good = await m15.run(ctx_good)
        r_bad = await m15.run(ctx_bad)
        assert r_bad.data["estimated_value"] < r_good.data["estimated_value"]

    async def test_no_tier_returns_error(self, m15):
        result = await m15.run({"completeness_ratio": 1.0})
        assert result.status == ModuleStatus.ERROR

    async def test_tier_icu_base(self, m15):
        result = await m15.run({
            "weight_profile": "tier_01",
            "mult_m4_word_count": 3.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 0.8,
        })
        assert result.data["tld_base"] == 5.0

    async def test_unknown_tier_defaults(self, m15):
        result = await m15.run({
            "weight_profile": "tier_00",
            "completeness_ratio": 1.0,
        })
        assert result.data["tld_base"] == 2.0

    async def test_range_widens_with_low_confidence(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "mult_m3_length": 2.0,
            "completeness_ratio": 0.3,
        }
        result = await m15.run(ctx)
        assert result.data["range"]["low"] < result.data["estimated_value"]
        assert result.data["range"]["high"] > result.data["estimated_value"]

    async def test_null_multipliers_omitted(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "mult_m3_length": 2.0,
            "mult_m4_word_count": None,
            "completeness_ratio": 1.0,
        }
        result = await m15.run(ctx)
        assert result.data["breakdown"]["m4_word_count"] is None

    async def test_com_abc_valuation(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "mult_m1_rdap": 3.0,
            "mult_m3_length": 8.0,
            "mult_m4_word_count": 20.0,
            "mult_m5_pronounceability": 1.5,
            "mult_m7_keyword_popularity": 5.0,
            "mult_m8_cpc": 1.0,
            "mult_m9_search_results": 5.0,
            "mult_m10_cross_tld": 1.0,
            "mult_m11_trademark": 1.0,
            "mult_m12_authority": 3.0,
            "completeness_ratio": 1.0,
        }
        result = await m15.run(ctx)
        value = result.data["estimated_value"]
        assert 3_000_000 <= value <= 6_000_000
