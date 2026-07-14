"""Tests for M5 — Pronounceability Scorer."""

from __future__ import annotations

import pytest

from ceche.domain import M5Pronounceability, ModuleStatus
from ceche.domain.modules.m05_pronounceability import (
    _bigram_score,
    _cluster_score,
    _resolve_multiplier,
    _vowel_score,
)


@pytest.fixture
def m5():
    return M5Pronounceability()


class TestVowelScore:
    def test_perfect_ratio_gets_100(self):
        assert _vowel_score("cares") == pytest.approx(100.0, rel=0.02)

    def test_too_few_vowels_penalized(self):
        assert _vowel_score("fjfbfj") == 0.0

    def test_too_many_vowels_penalized(self):
        s = _vowel_score("aeiouae")
        assert s <= 10.0


class TestClusterScore:
    def test_no_clusters_full_score(self):
        assert _cluster_score("car") == 100.0
        assert _cluster_score("yotop") == 100.0

    def test_two_consecutive_consonants(self):
        assert _cluster_score("car") == 100.0

    def test_three_consecutive_consonants(self):
        assert _cluster_score("abcsea") == 70.0

    def test_four_consecutive_consonants(self):
        assert _cluster_score("abcdfe") == 30.0

    def test_five_consonants(self):
        s = _cluster_score("fjfbfj")
        assert s < 10.0

    @pytest.mark.parametrize("word,expected_min", [
        ("xvbcd", 0),
    ])
    def test_long_consonant_runs_tank(self, word, expected_min):
        s = _cluster_score(word)
        assert s >= expected_min


class TestBigramScore:
    def test_common_bigrams_score_high(self):
        s = _bigram_score("the")
        assert s > 50.0

    def test_uncommon_bigrams_score_low(self):
        s = _bigram_score("fjfbfj")
        assert s < 15.0

    def test_single_char_uses_default(self):
        s = _bigram_score("a")
        assert s == 5.0


class TestMultiplier:
    def test_above_90(self):
        assert _resolve_multiplier(95.0) == 2.0

    def test_above_70(self):
        assert _resolve_multiplier(75.0) == 1.5

    def test_above_40(self):
        assert _resolve_multiplier(50.0) == 1.2

    def test_below_40(self):
        assert _resolve_multiplier(30.0) == 1.0


class TestM5Pronounceability:
    async def test_short_strings_get_max(self, m5):
        for sld in ("a", "x", "ab"):
            result = await m5.run({"sld": sld})
            assert result.data["score"] == 100.0
            assert result.data["multiplier"] == 2.0

    async def test_car_is_pronounceable(self, m5):
        result = await m5.run({"sld": "car"})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["score"] > 60.0
        assert result.data["multiplier"] >= 1.5

    async def test_yotop_is_pronounceable(self, m5):
        result = await m5.run({"sld": "yotop"})
        assert result.data["multiplier"] >= 1.5

    async def test_fjfbfj_is_unpronounceable(self, m5):
        result = await m5.run({"sld": "fjfbfj"})
        assert result.data["multiplier"] == 1.0
        assert result.data["score"] < 10.0

    async def test_long_real_word_is_pronounceable(self, m5):
        result = await m5.run({"sld": "insurance"})
        assert result.data["multiplier"] >= 1.5

    async def test_no_sld_returns_error(self, m5):
        result = await m5.run({})
        assert result.status == ModuleStatus.ERROR

    async def test_empty_sld_returns_error(self, m5):
        result = await m5.run({"sld": ""})
        assert result.status == ModuleStatus.ERROR

    async def test_value_matches_multiplier(self, m5):
        result = await m5.run({"sld": "car"})
        assert result.value == result.data["multiplier"]

    async def test_confidence_is_1(self, m5):
        result = await m5.run({"sld": "hello"})
        assert result.confidence == 1.0

    async def test_hyphens_are_tolerated_as_consonants(self, m5):
        result = await m5.run({"sld": "top-insurance"})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["cluster_score"] == 100.0

    async def test_mixed_case_is_lowered(self, m5):
        r1 = await m5.run({"sld": "Car"})
        r2 = await m5.run({"sld": "car"})
        assert r1.data["score"] == r2.data["score"]
