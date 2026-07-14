"""Tests for M15 — Pricing with scarcity-based dynamic base."""

from __future__ import annotations

import pytest

from ceche.domain import M15Pricing, ModuleStatus


@pytest.fixture
def m15():
    return M15Pricing()


class TestM15Pricing:
    async def test_car_com_scarcity_driven(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "sld": "car",
            "word_count": 1,
            "registered": True,
            "m6_status": "split_found",
            "mult_m1_rdap": 3.0,
            "mult_m5_pronounceability": 2.0,
            "mult_m7_keyword_popularity": 8.0,
            "mult_m8_cpc": 5.0,
            "mult_m12_authority": 3.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 1.0,
        }
        result = await m15.run(ctx)
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["estimated_value"] > 5_000_000

    async def test_nachase_com_mid_tier(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "sld": "nachase",
            "word_count": 2,
            "registered": True,
            "m6_status": "split_found",
            "mult_m1_rdap": 1.5,
            "mult_m5_pronounceability": 1.5,
            "mult_m7_keyword_popularity": 1.5,
            "mult_m8_cpc": 1.0,
            "mult_m12_authority": 2.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 1.0,
        }
        result = await m15.run(ctx)
        assert 10_000 <= result.data["estimated_value"] <= 100_000

    async def test_brandable_scarcity(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "sld": "nekwasa",
            "word_count": None,
            "registered": False,
            "m6_status": "no_split",
            "mult_m5_pronounceability": 1.5,
            "mult_m16_brandability": 5.0,
            "mult_m7_keyword_popularity": 1.0,
            "mult_m8_cpc": 1.0,
            "mult_m10_cross_tld": 1.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 0.5,
        }
        result = await m15.run(ctx)
        assert result.data["estimated_value"] > 500

    async def test_fjfbfj_near_zero(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "sld": "fjfbfj",
            "word_count": None,
            "registered": False,
            "m6_status": "no_split",
            "mult_m5_pronounceability": 1.0,
            "mult_m16_brandability": 1.0,
            "mult_m7_keyword_popularity": 1.0,
            "mult_m8_cpc": 1.0,
            "mult_m10_cross_tld": 1.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 1.0,
        }
        result = await m15.run(ctx)
        assert result.data["estimated_value"] < 20_000

    async def test_icu_tld_punishes(self, m15):
        ctx = {
            "weight_profile": "tier_01",
            "sld": "car",
            "word_count": 1,
            "registered": False,
            "m6_status": "split_found",
            "mult_m5_pronounceability": 2.0,
            "mult_m7_keyword_popularity": 8.0,
            "mult_m8_cpc": 5.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 1.0,
        }
        result = await m15.run(ctx)
        assert result.data["estimated_value"] > 100_000

    async def test_scarcity_base_shown(self, m15):
        ctx = {
            "weight_profile": "tier_10",
            "sld": "car",
            "word_count": 1,
            "registered": True,
            "m6_status": "split_found",
            "mult_m1_rdap": 3.0,
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 1.0,
        }
        result = await m15.run(ctx)
        assert "scarcity_base" in result.data
        assert result.data["scarcity_base"] >= 5_000_000

    async def test_trademark_penalty(self, m15):
        ctx_clean = {
            "weight_profile": "tier_10",
            "sld": "car",
            "word_count": 1,
            "registered": True,
            "m6_status": "split_found",
            "mult_m11_trademark": 1.0,
            "completeness_ratio": 1.0,
        }
        ctx_bad = {**ctx_clean, "mult_m11_trademark": 0.1}
        r_clean = await m15.run(ctx_clean)
        r_bad = await m15.run(ctx_bad)
        assert r_bad.data["estimated_value"] < r_clean.data["estimated_value"]

    async def test_no_profile_returns_error(self, m15):
        result = await m15.run({"completeness_ratio": 1.0})
        assert result.status == ModuleStatus.ERROR
