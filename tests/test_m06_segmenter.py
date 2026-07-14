"""Tests for M6 — Segmenter (Word-Break)."""

from __future__ import annotations

import pytest

from ceche.domain import M6Segmenter, ModuleStatus
from ceche.domain.modules.m06_segmenter import _segment


@pytest.fixture
def m6():
    return M6Segmenter()


class TestSegmenterSplits:
    def test_single_common_word(self):
        assert _segment("car") == ["car"]
        assert _segment("insurance") == ["insurance"]

    def test_two_word_split(self):
        assert _segment("topinsurance") == ["top", "insurance"]
        assert _segment("bestcar") == ["best", "car"]

    def test_three_word_split(self):
        result = _segment("sadmecry")
        assert result is not None
        assert len(result) == 3
        assert "sad" in result or "sad" in "".join(result)
        assert "cry" in result or "cry" in "".join(result)

    def test_gibberish_returns_none(self):
        assert _segment("fjfbfj") is None

    def test_brand_name_single_word(self):
        assert _segment("godaddy") == ["godaddy"]
        assert _segment("business") == ["business"]

    def test_brandable_coinage(self):
        assert _segment("yotop") == ["yo", "top"]


class TestM6Segmenter:
    async def test_successful_split(self, m6):
        result = await m6.run({"sld": "topinsurance"})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["winner"] == ["top", "insurance"]
        assert result.data["word_count"] == 2
        assert result.data["confidence"] >= 0.8

    async def test_single_word(self, m6):
        result = await m6.run({"sld": "car"})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["word_count"] == 1

    async def test_no_split(self, m6):
        result = await m6.run({"sld": "fjfbfj"})
        assert result.status == ModuleStatus.SKIPPED
        assert result.data["winner"] is None
        assert result.data["word_count"] is None
        assert result.data["status"] == "no_split"

    async def test_no_sld_returns_error(self, m6):
        result = await m6.run({})
        assert result.status == ModuleStatus.ERROR

    async def test_value_is_none_on_success(self, m6):
        result = await m6.run({"sld": "insurance"})
        assert result.value is None

    async def test_data_contains_status_field(self, m6):
        result = await m6.run({"sld": "topinsurance"})
        assert "status" in result.data
        assert result.data["status"] == "split_found"

    async def test_confidence_reasonable(self, m6):
        result = await m6.run({"sld": "topinsurance"})
        assert 0.0 <= result.confidence <= 1.0

    async def test_case_insensitive(self, m6):
        r1 = await m6.run({"sld": "Car"})
        r2 = await m6.run({"sld": "car"})
        assert r1.data["winner"] == r2.data["winner"]

    async def test_empty_sld_returns_error(self, m6):
        result = await m6.run({"sld": ""})
        assert result.status == ModuleStatus.ERROR
