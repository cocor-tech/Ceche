"""Tests for M8 — CPC / Commercial-Intent Scorer."""

from __future__ import annotations

import pytest

from ceche.domain import M8CPC, ModuleStatus


@pytest.fixture
def m8():
    return M8CPC()


class TestM8CPC:
    async def test_elite_word(self, m8):
        result = await m8.run({"words": ["insurance"]})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["tier"] == "elite"
        assert result.data["multiplier"] == 5.0

    async def test_high_word(self, m8):
        result = await m8.run({"words": ["hosting"]})
        assert result.data["tier"] == "high"
        assert result.data["multiplier"] == 3.0

    async def test_medium_high_word(self, m8):
        result = await m8.run({"words": ["marketing"]})
        assert result.data["tier"] == "medium_high"
        assert result.data["multiplier"] == 2.5

    async def test_medium_word(self, m8):
        result = await m8.run({"words": ["fitness"]})
        assert result.data["tier"] == "medium"
        assert result.data["multiplier"] == 2.0

    async def test_low_word(self, m8):
        result = await m8.run({"words": ["blog"]})
        assert result.data["tier"] == "low"
        assert result.data["multiplier"] == 1.5

    async def test_informational_word(self, m8):
        result = await m8.run({"words": ["how"]})
        assert result.data["tier"] == "informational"
        assert result.data["multiplier"] == 1.0

    async def test_unknown_word_defaults_none(self, m8):
        result = await m8.run({"words": ["xyzzy"]})
        assert result.data["tier"] == "none"
        assert result.data["multiplier"] == 1.0

    async def test_highest_tier_survives(self, m8):
        result = await m8.run({"words": ["blog", "insurance", "how"]})
        assert result.data["tier"] == "elite"
        assert result.data["match_word"] == "insurance"

    async def test_case_insensitive(self, m8):
        r1 = await m8.run({"words": ["Insurance"]})
        r2 = await m8.run({"words": ["insuraNCE"]})
        assert r1.data["tier"] == "elite"
        assert r2.data["tier"] == "elite"

    async def test_empty_words_returns_skipped(self, m8):
        result = await m8.run({"words": []})
        assert result.status == ModuleStatus.SKIPPED

    async def test_no_words_returns_skipped(self, m8):
        result = await m8.run({})
        assert result.status == ModuleStatus.SKIPPED

    async def test_invalid_words_returns_error(self, m8):
        result = await m8.run({"words": "not_a_list"})
        assert result.status == ModuleStatus.ERROR

    async def test_match_word_set_to_highest(self, m8):
        result = await m8.run({"words": ["fun", "loans", "blog"]})
        assert result.data["match_word"] == "loans"

    async def test_unknown_word_gives_low_confidence(self, m8):
        result = await m8.run({"words": ["xyzzy"]})
        assert result.confidence == 0.5

    async def test_known_word_gives_high_confidence(self, m8):
        result = await m8.run({"words": ["insurance"]})
        assert result.confidence == 1.0
