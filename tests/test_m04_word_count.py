"""Tests for M4 — Word-Count Scorer."""

from __future__ import annotations

import math

import pytest

from ceche.domain import M4WordCount, ModuleStatus
from ceche.domain.modules.m04_word_count import _compute_score, _resolve_multiplier


@pytest.fixture
def m4():
    return M4WordCount()


class TestM4ComputeScore:
    def test_one_word_max_score(self):
        score = _compute_score(1)
        assert score >= 99.0

    def test_two_words_drop(self):
        expected = 100.0 * math.exp(-0.5 * 1)
        score = _compute_score(2)
        assert abs(score - expected) < 0.01

    def test_three_words(self):
        score = _compute_score(3)
        assert 35.0 <= score <= 38.0

    def test_four_words(self):
        score = _compute_score(4)
        assert 20.0 <= score <= 23.0

    def test_five_words_low(self):
        score = _compute_score(5)
        assert 10.0 <= score <= 15.0

    def test_many_words_approaches_zero(self):
        score = _compute_score(10)
        assert score < 2.0

    def test_monotonically_decreasing(self):
        scores = [_compute_score(n) for n in range(1, 15)]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]


class TestM4ResolveMultiplier:
    def test_one_word_multiplier_20(self):
        assert _resolve_multiplier(1) == 20.0

    def test_two_words_multiplier_3(self):
        assert _resolve_multiplier(2) == 3.0

    def test_three_words_multiplier_1_5(self):
        assert _resolve_multiplier(3) == 1.5

    def test_four_words_multiplier_1(self):
        assert _resolve_multiplier(4) == 1.0

    def test_five_words_multiplier_1(self):
        assert _resolve_multiplier(5) == 1.0

    def test_hundred_words_multiplier_1(self):
        assert _resolve_multiplier(100) == 1.0


class TestM4WordCount:
    async def test_one_word_domain(self, m4):
        result = await m4.run({"word_count": 1})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["word_count"] == 1
        assert result.data["score"] >= 99.0
        assert result.data["multiplier"] == 20.0

    async def test_two_word_domain(self, m4):
        result = await m4.run({"word_count": 2})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["word_count"] == 2
        assert result.data["multiplier"] == 3.0

    async def test_three_word_domain(self, m4):
        result = await m4.run({"word_count": 3})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["multiplier"] == 1.5

    async def test_four_word_domain(self, m4):
        result = await m4.run({"word_count": 4})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["multiplier"] == 1.0

    async def test_many_words_multiplier_stays_1(self, m4):
        result = await m4.run({"word_count": 7})
        assert result.data["multiplier"] == 1.0

    async def test_no_word_count_returns_skipped(self, m4):
        result = await m4.run({"word_count": None})
        assert result.status == ModuleStatus.SKIPPED
        assert result.value is None

    async def test_missing_word_count_returns_skipped(self, m4):
        result = await m4.run({})
        assert result.status == ModuleStatus.SKIPPED
        assert result.value is None

    async def test_value_matches_multiplier(self, m4):
        result = await m4.run({"word_count": 1})
        assert result.value == 20.0

    async def test_confidence_is_1_on_success(self, m4):
        result = await m4.run({"word_count": 1})
        assert result.confidence == 1.0

    async def test_invalid_word_count_returns_error(self, m4):
        result = await m4.run({"word_count": "abc"})
        assert result.status == ModuleStatus.ERROR

    async def test_negative_word_count_returns_error(self, m4):
        result = await m4.run({"word_count": -1})
        assert result.status == ModuleStatus.ERROR

    async def test_zero_word_count_returns_error(self, m4):
        result = await m4.run({"word_count": 0})
        assert result.status == ModuleStatus.ERROR
