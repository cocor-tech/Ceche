"""Tests for M7 — Keyword Popularity Lookup."""

from __future__ import annotations

import pytest

from ceche.domain import M7KeywordPopularity, ModuleStatus
from ceche.domain.modules.m07_keyword_popularity import _resolve_multiplier
from ceche.infrastructure.keyword.static_adapter import StaticKeywordAdapter


@pytest.fixture
def adapter():
    return StaticKeywordAdapter()


@pytest.fixture
def m7(adapter):
    return M7KeywordPopularity(adapter)


class TestResolveMultiplier:
    def test_above_90(self):
        assert _resolve_multiplier(95.0) == 8.0

    def test_above_70(self):
        assert _resolve_multiplier(75.0) == 5.0

    def test_above_50(self):
        assert _resolve_multiplier(55.0) == 3.0

    def test_above_30(self):
        assert _resolve_multiplier(35.0) == 2.0

    def test_above_10(self):
        assert _resolve_multiplier(15.0) == 1.5

    def test_below_10(self):
        assert _resolve_multiplier(5.0) == 1.0

    def test_zero(self):
        assert _resolve_multiplier(0.0) == 1.0


class TestStaticAdapter:
    async def test_common_word_returns_score(self, adapter):
        score = await adapter.get_popularity("insurance")
        assert score > 0

    async def test_gibberish_returns_zero(self, adapter):
        score = await adapter.get_popularity("fjfbfj")
        assert score == 0.0


class TestM7KeywordPopularity:
    async def test_single_word(self, m7):
        result = await m7.run({"words": ["top"]})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["domain_score"] > 10
        assert result.data["multiplier"] >= 1.5

    async def test_multiple_words_returns_max(self, m7):
        result = await m7.run({"words": ["car", "insurance"]})
        assert result.data["domain_score"] >= max(
            result.data["word_scores"].values()
        )

    async def test_gibberish_words(self, m7):
        result = await m7.run({"words": ["fjfbfj", "xyzzy"]})
        assert result.data["domain_score"] == 0.0
        assert result.data["multiplier"] == 1.0

    async def test_no_words_returns_skipped(self, m7):
        result = await m7.run({})
        assert result.status == ModuleStatus.SKIPPED

    async def test_empty_words_returns_skipped(self, m7):
        result = await m7.run({"words": []})
        assert result.status == ModuleStatus.SKIPPED

    async def test_invalid_words_returns_error(self, m7):
        result = await m7.run({"words": "not_a_list"})
        assert result.status == ModuleStatus.ERROR

    async def test_value_matches_multiplier(self, m7):
        result = await m7.run({"words": ["insurance"]})
        assert result.value == result.data["multiplier"]

    async def test_word_scores_is_dict(self, m7):
        result = await m7.run({"words": ["car", "blog"]})
        scores = result.data["word_scores"]
        assert "car" in scores
        assert "blog" in scores

    async def test_confidence_increases_with_valid_words(self, m7):
        r1 = await m7.run({"words": ["car", "blog"]})
        r2 = await m7.run({"words": ["fjfbfj", "xyzzy"]})
        assert r1.confidence > r2.confidence
