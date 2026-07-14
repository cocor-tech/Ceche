"""Tests for M13 — Confidence / Data-Completeness Flag."""

from __future__ import annotations

import pytest

from ceche.domain import M13Confidence, ModuleStatus


@pytest.fixture
def m13():
    return M13Confidence()


def _result(status: ModuleStatus):
    return {"status": status}


class TestM13Confidence:
    async def test_all_modules_success(self, m13):
        ctx = {}
        for name in [
            "m1_rdap", "m2_tld_table", "m3_length", "m4_word_count",
            "m5_pronounceability", "m6_segmenter", "m7_keyword_popularity",
            "m8_cpc", "m9_search_results", "m10_cross_tld",
            "m11_trademark", "m12_authority",
        ]:
            ctx[f"result_{name}"] = _result(ModuleStatus.SUCCESS)

        result = await m13.run(ctx)
        assert result.data["completeness_ratio"] == 1.0
        assert result.data["label"] == "high"

    async def test_half_modules_success(self, m13):
        ctx = {}
        names = [
            "m1_rdap", "m2_tld_table", "m3_length", "m4_word_count",
            "m5_pronounceability", "m6_segmenter", "m7_keyword_popularity",
            "m8_cpc", "m9_search_results", "m10_cross_tld",
            "m11_trademark", "m12_authority",
        ]
        for i, name in enumerate(names):
            ctx[f"result_{name}"] = _result(
                ModuleStatus.SUCCESS if i < 6 else ModuleStatus.ERROR,
            )

        result = await m13.run(ctx)
        assert 0.4 <= result.data["completeness_ratio"] <= 0.6

    async def test_no_modules_returns_zero(self, m13):
        result = await m13.run({})
        assert result.data["completeness_ratio"] == 0.0
        assert result.data["label"] == "none"

    async def test_value_is_ratio(self, m13):
        ctx = {
            "result_m2_tld_table": _result(ModuleStatus.SUCCESS),
            "result_m3_length": _result(ModuleStatus.SUCCESS),
        }
        result = await m13.run(ctx)
        assert result.value == 1.0

    async def test_label_high(self, m13):
        ctx = {
            "result_m2_tld_table": _result(ModuleStatus.SUCCESS),
            "result_m3_length": _result(ModuleStatus.SUCCESS),
            "result_m4_word_count": _result(ModuleStatus.SUCCESS),
            "result_m5_pronounceability": _result(ModuleStatus.SUCCESS),
            "result_m6_segmenter": _result(ModuleStatus.SUCCESS),
            "result_m7_keyword_popularity": _result(ModuleStatus.SUCCESS),
            "result_m8_cpc": _result(ModuleStatus.SUCCESS),
            "result_m9_search_results": _result(ModuleStatus.SUCCESS),
            "result_m10_cross_tld": _result(ModuleStatus.SUCCESS),
            "result_m11_trademark": _result(ModuleStatus.SUCCESS),
        }
        result = await m13.run(ctx)
        assert result.data["label"] == "high"

    async def test_label_medium(self, m13):
        ctx = {}
        names = [
            "m2_tld_table", "m3_length", "m4_word_count",
            "m5_pronounceability", "m6_segmenter",
            "m7_keyword_popularity", "m8_cpc",
        ]
        for i, name in enumerate(names):
            ctx[f"result_{name}"] = _result(
                ModuleStatus.SUCCESS if i < 5 else ModuleStatus.ERROR,
            )

        result = await m13.run(ctx)
        assert result.data["label"] == "medium"

    async def test_label_low(self, m13):
        ctx = {}
        names = [
            "m2_tld_table", "m3_length", "m4_word_count",
        ]
        for i, name in enumerate(names):
            ctx[f"result_{name}"] = _result(
                ModuleStatus.SUCCESS if i < 2 else ModuleStatus.ERROR,
            )

        result = await m13.run(ctx)
        assert result.data["label"] == "low"
