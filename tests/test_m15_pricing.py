"""Tests for M15 — Pricing Module (weighted exponentiation)."""

from __future__ import annotations

import pytest

from ceche.domain import M15Pricing, ModuleStatus


@pytest.fixture
def m15():
    return M15Pricing()


class TestM15Pricing:
    async def test_com_registered_weighted(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "registered": True,
            "mult_m1_rdap": 3.0,
            "mult_m3_length": 15.0,
            "mult_m4_word_count": 20.0,
            "mult_m5_pronounceability": 2.0,
            "mult_m7_keyword_popularity": 8.0,
            "mult_m8_cpc": 1.0,
            "mult_m10_cross_tld": 1.0,
            "mult_m11_trademark": 1.0,
            "mult_m12_authority": 3.0,
            "completeness_ratio": 1.0,
        }
        result = await m15.run(ctx)
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["estimated_value"] > 500_000

    async def test_com_unregistered_weights_normalized(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "registered": False,
            "mult_m3_length": 2.0,
            "mult_m4_word_count": 3.0,
            "mult_m5_pronounceability": 1.5,
            "mult_m7_keyword_popularity": 5.0,
            "mult_m8_cpc": 1.0,
            "mult_m10_cross_tld": 1.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 0.8,
        }
        result = await m15.run(ctx)
        assert result.data["estimated_value"] > 0

    async def test_brandable_fallback_used(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "m6_status": "no_split",
            "registered": False,
            "mult_m3_length": 2.0,
            "mult_m5_pronounceability": 1.5,
            "mult_m16_brandability": 5.0,
            "mult_m7_keyword_popularity": 1.0,
            "mult_m8_cpc": 1.0,
            "mult_m10_cross_tld": 1.0,
            "completeness_ratio": 0.5,
        }
        result = await m15.run(ctx)
        assert "m16_brandability" in result.data["breakdown"]
        assert result.data["range"]["low"] < result.data["range"]["high"]

    async def test_weighted_differs_from_blind(self, m15):
        ctx_blind = {
            "weight_profile": "tier_00",
            "registered": False,
            "mult_m3_length": 15.0,
            "mult_m4_word_count": 20.0,
            "mult_m8_cpc": 1.0,
            "mult_m7_keyword_popularity": 1.0,
            "mult_m5_pronounceability": 2.0,
            "mult_m10_cross_tld": 1.0,
            "completeness_ratio": 1.0,
        }
        ctx_weighted = {
            "weight_profile": "tier_10",
            "registered": True,
            "mult_m1_rdap": 1.0,
            "mult_m3_length": 15.0,
            "mult_m4_word_count": 20.0,
            "mult_m5_pronounceability": 2.0,
            "mult_m7_keyword_popularity": 1.0,
            "mult_m8_cpc": 1.0,
            "mult_m10_cross_tld": 1.0,
            "mult_m11_trademark": 1.0,
            "mult_m12_authority": 1.0,
            "completeness_ratio": 1.0,
        }
        r_default = await m15.run(ctx_blind)
        r_tier10 = await m15.run(ctx_weighted)
        assert r_default.data["estimated_value"] != r_tier10.data["estimated_value"]

    async def test_word_count_dominates_in_tier_10(self, m15):
        ctx_high = {
            "weight_profile": "tier_10",
            "registered": False,
            "mult_m3_length": 2.0,
            "mult_m4_word_count": 20.0,
            "completeness_ratio": 1.0,
        }
        ctx_low = {
            "weight_profile": "tier_10",
            "registered": False,
            "mult_m3_length": 2.0,
            "mult_m4_word_count": 1.0,
            "completeness_ratio": 1.0,
        }
        r_high = await m15.run(ctx_high)
        r_low = await m15.run(ctx_low)
        assert r_high.data["estimated_value"] > r_low.data["estimated_value"]

    async def test_trademark_multiplier_punishes(self, m15):
        ctx_clean = {
            "weight_profile": "tier_10",
            "registered": False,
            "mult_m4_word_count": 20.0,
            "mult_m3_length": 15.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 1.0,
        }
        ctx_bad = {**ctx_clean, "mult_m11_trademark": 0.1}
        r_clean = await m15.run(ctx_clean)
        r_bad = await m15.run(ctx_bad)
        assert r_bad.data["estimated_value"] < r_clean.data["estimated_value"]

    async def test_icu_base_is_200(self, m15):
        result = await m15.run({
            "weight_profile": "tier_01",
            "registered": False,
            "mult_m4_word_count": 3.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 0.8,
        })
        assert result.data["tld_base"] == 200.0

    async def test_no_weight_profile_returns_error(self, m15):
        result = await m15.run({"completeness_ratio": 1.0})
        assert result.status == ModuleStatus.ERROR

    async def test_abc_com_weighted_valuation(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "registered": True,
            "mult_m1_rdap": 3.0,
            "mult_m3_length": 8.0,
            "mult_m4_word_count": 20.0,
            "mult_m5_pronounceability": 1.5,
            "mult_m7_keyword_popularity": 5.0,
            "mult_m8_cpc": 1.0,
            "mult_m10_cross_tld": 1.0,
            "mult_m11_trademark": 1.0,
            "mult_m12_authority": 3.0,
            "completeness_ratio": 1.0,
        }
        result = await m15.run(ctx)
        value = result.data["estimated_value"]
        assert 500_000 <= value <= 5_000_000
