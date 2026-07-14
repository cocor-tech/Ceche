"""Tests for M3 — Character Length Scorer."""

from __future__ import annotations

import math

import pytest

from ceche.domain import M3Length, ModuleStatus
from ceche.domain.modules.m03_length import _compute_score, _resolve_multiplier


@pytest.fixture
def m3():
    return M3Length()


class TestM3ComputeScore:
    def test_length_1_near_max(self):
        score = _compute_score(1)
        assert score >= 95.0

    def test_length_2_scoring(self):
        score = _compute_score(2)
        assert 90.0 <= score <= 95.0

    def test_length_3_scoring(self):
        score = _compute_score(3)
        assert 80.0 <= score <= 86.0

    def test_length_4_scoring(self):
        score = _compute_score(4)
        assert 65.0 <= score <= 72.0

    def test_length_5_midpoint(self):
        score = _compute_score(5)
        assert 49.0 <= score <= 51.0

    def test_length_6_drops(self):
        score = _compute_score(6)
        assert 29.0 <= score <= 33.0

    def test_length_8_low(self):
        score = _compute_score(8)
        assert 7.0 <= score <= 10.0

    def test_length_10_very_low(self):
        score = _compute_score(10)
        assert 1.0 <= score <= 3.0

    def test_length_15_very_low(self):
        score = _compute_score(15)
        assert score <= 10.0

    def test_zero_length_returns_zero(self):
        score = _compute_score(0)
        assert score == 0.0

    def test_monotonically_decreasing(self):
        scores = [_compute_score(n) for n in range(1, 30)]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], f"score dropped at index {i}"

    def test_know_value_3(self):
        score = _compute_score(3)
        expected = 100.0 * (1.0 - 1.0 / (1.0 + math.exp(-0.8 * (3 - 5))))
        assert abs(score - expected) < 0.01

    def test_know_value_10(self):
        score = _compute_score(10)
        expected = 100.0 * (1.0 - 1.0 / (1.0 + math.exp(-0.8 * (10 - 5))))
        assert abs(score - expected) < 0.01


class TestM3ResolveMultiplier:
    def test_score_100_multiplier_15(self):
        assert _resolve_multiplier(100.0) == 15.0

    def test_score_95_multiplier_15(self):
        assert _resolve_multiplier(95.0) == 15.0

    def test_score_90_multiplier_8(self):
        assert _resolve_multiplier(90.0) == 8.0

    def test_score_75_multiplier_8(self):
        assert _resolve_multiplier(75.0) == 8.0

    def test_score_60_multiplier_2(self):
        assert _resolve_multiplier(60.0) == 2.0

    def test_score_50_multiplier_2(self):
        assert _resolve_multiplier(50.0) == 2.0

    def test_score_30_multiplier_1_2(self):
        assert _resolve_multiplier(30.0) == 1.2

    def test_score_25_multiplier_1_2(self):
        assert _resolve_multiplier(25.0) == 1.2

    def test_score_10_multiplier_1(self):
        assert _resolve_multiplier(10.0) == 1.0

    def test_score_0_multiplier_1(self):
        assert _resolve_multiplier(0.0) == 1.0


class TestM3Length:
    async def test_sld_in_context(self, m3):
        result = await m3.run({"sld": "abc"})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["raw_length"] == 3
        assert result.data["multiplier"] == 8.0

    async def test_sld_3_letters_scores_8_mult(self, m3):
        result = await m3.run({"sld": "a"})
        assert result.data["multiplier"] == 15.0

    async def test_long_sld_drops_multiplier(self, m3):
        result = await m3.run({"sld": "abcdefghijklmno"})
        assert result.data["raw_length"] == 15
        assert result.data["multiplier"] == 1.0

    async def test_long_sld_score_below_10(self, m3):
        result = await m3.run({"sld": "abcdefghijklmno"})
        assert result.data["score"] < 10.0

    async def test_no_sld_returns_error(self, m3):
        result = await m3.run({})
        assert result.status == ModuleStatus.ERROR

    async def test_value_matches_multiplier(self, m3):
        result = await m3.run({"sld": "a"})
        assert result.value == 15.0
        result2 = await m3.run({"sld": "abc"})
        assert result2.value == 8.0

    async def test_confidence_is_always_1(self, m3):
        result = await m3.run({"sld": "test"})
        assert result.confidence == 1.0

    async def test_score_increases_as_length_decreases(self, m3):
        r3 = await m3.run({"sld": "aaa"})
        r6 = await m3.run({"sld": "aaaaaa"})
        r10 = await m3.run({"sld": "aaaaaaaaaa"})
        assert r3.data["score"] > r6.data["score"] > r10.data["score"]

    async def test_empty_sld_still_has_error(self, m3):
        result = await m3.run({"sld": ""})
        assert result.status == ModuleStatus.ERROR

    async def test_hyphens_counted_in_length(self, m3):
        result = await m3.run({"sld": "a-b-c"})
        assert result.data["raw_length"] == 5

    async def test_numeric_same_as_letters(self, m3):
        r_alpha = await m3.run({"sld": "abcde"})
        r_numeric = await m3.run({"sld": "12345"})
        assert r_alpha.data["score"] == r_numeric.data["score"]
