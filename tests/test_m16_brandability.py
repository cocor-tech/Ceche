"""Tests for M16 — Brandability Scorer."""

from __future__ import annotations

import pytest

from ceche.domain import M16Brandability, ModuleStatus
from ceche.domain.modules.m16_brandability import (
    _length_score,
    _pattern_score,
    _resolve_multiplier,
    _syllable_flow,
)


@pytest.fixture
def m16():
    return M16Brandability()


class TestSyllableFlow:
    def test_two_syllables_ideal(self):
        assert _syllable_flow("neko") == pytest.approx(100.0)

    def test_three_syllables_good(self):
        assert _syllable_flow("nekowa") == pytest.approx(90.0)

    def test_one_syllable_ok(self):
        assert _syllable_flow("car") == pytest.approx(40.0)

    def test_no_vowels_bad(self):
        assert _syllable_flow("fjfbfj") == pytest.approx(0.0)


class TestPatternScore:
    def test_no_pattern_base(self):
        assert _pattern_score("abcd") >= 30

    def test_io_ending_bonus(self):
        s1 = _pattern_score("nekio")
        s2 = _pattern_score("abcd")
        assert s1 > s2


class TestLengthScore:
    def test_ideal_range_full(self):
        assert _length_score(5) == 100.0

    def test_short_penalized(self):
        assert _length_score(2) < 60.0

    def test_long_penalized(self):
        assert _length_score(10) < 80.0


class TestMultiplier:
    def test_above_80(self):
        assert _resolve_multiplier(85.0) == 8.0

    def test_above_60(self):
        assert _resolve_multiplier(65.0) == 5.0

    def test_above_40(self):
        assert _resolve_multiplier(45.0) == 3.0

    def test_above_20(self):
        assert _resolve_multiplier(25.0) == 2.0

    def test_below_20(self):
        assert _resolve_multiplier(10.0) == 1.0


class TestM16Brandability:
    async def test_brandable_name(self, m16):
        result = await m16.run({"sld": "nekowi"})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["multiplier"] >= 3.0

    async def test_medium_brandable(self, m16):
        result = await m16.run({"sld": "yotop"})
        assert result.data["multiplier"] >= 2.0

    async def test_gibberish_low(self, m16):
        result = await m16.run({"sld": "fjfbfj"})
        assert result.data["multiplier"] == 1.0

    async def test_skips_when_m6_found_split(self, m16):
        result = await m16.run({"sld": "car", "m6_status": "split_found"})
        assert result.status == ModuleStatus.SKIPPED
        assert result.value is None

    async def test_no_sld_returns_error(self, m16):
        result = await m16.run({})
        assert result.status == ModuleStatus.ERROR

    async def test_value_is_multiplier(self, m16):
        result = await m16.run({"sld": "nekowi"})
        assert result.value == result.data["multiplier"]
