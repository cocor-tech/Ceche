"""Tests for M11 — Trademark Check (with full-SLD check)."""

from __future__ import annotations

import pytest

from ceche.domain import M11Trademark, ModuleStatus
from ceche.infrastructure.trademark.uspto_adapter import USPTOAdapter


@pytest.fixture
def adapter():
    return USPTOAdapter()


@pytest.fixture
def m11(adapter):
    return M11Trademark(adapter)


class TestUSPTOAdapter:
    async def test_known_mark_detected(self, adapter):
        result = await adapter.check("google")
        assert result.conflict is True
        assert result.severity == "exact"
        assert "Google" in result.marks

    async def test_generic_word_no_conflict(self, adapter):
        result = await adapter.check("car")
        assert result.conflict is False
        assert result.severity == "none"

    async def test_unknown_word_no_conflict(self, adapter):
        result = await adapter.check("xyzzy1234")
        assert result.conflict is False

    async def test_case_insensitive(self, adapter):
        r1 = await adapter.check("Google")
        r2 = await adapter.check("google")
        assert r1.conflict == r2.conflict


class TestM11Trademark:
    async def test_single_known_mark(self, m11):
        result = await m11.run({"sld": "google", "words": ["google"]})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["severity"] == "exact"
        assert result.data["multiplier"] == 0.1

    async def test_no_conflict(self, m11):
        result = await m11.run({"sld": "car", "words": ["car"]})
        assert result.data["severity"] == "none"
        assert result.data["multiplier"] == 1.0

    async def test_multiple_words_exact_wins(self, m11):
        result = await m11.run({"sld": "google", "words": ["car", "google", "blog"]})
        assert result.data["severity"] == "exact"

    async def test_full_sld_catches_trademark(self, m11):
        result = await m11.run({"sld": "godaddy", "words": ["go", "daddy"]})
        assert result.data["severity"] == "exact"

    async def test_no_sld_returns_error(self, m11):
        result = await m11.run({})
        assert result.status == ModuleStatus.ERROR

    async def test_value_is_multiplier(self, m11):
        result = await m11.run({"sld": "google", "words": ["google"]})
        assert result.value == 0.1

    async def test_falls_back_on_error(self, adapter):
        class _Failing:
            async def check(self, term: str):
                raise RuntimeError("fail")
        m11 = M11Trademark(_Failing(), adapter)
        result = await m11.run({"sld": "google"})
        assert result.data["multiplier"] == 0.1

    async def test_sld_checked_even_without_words(self, adapter):
        m11 = M11Trademark(adapter)
        result = await m11.run({"sld": "google"})
        assert result.data["severity"] == "exact"

    async def test_single_word_com_trademark_unpenalized(self, adapter):
        m11 = M11Trademark(adapter)
        result = await m11.run({"sld": "disney", "words": ["disney"], "tld": "com", "word_count": 1})
        assert result.data["severity"] == "none"
        assert result.data["multiplier"] == 1.0

    async def test_multi_word_trademark_still_penalized(self, adapter):
        m11 = M11Trademark(adapter)
        result = await m11.run({"sld": "googletest", "words": ["google", "test"], "tld": "com", "word_count": 2})
        assert result.data["severity"] == "exact"

    async def test_non_com_trademark_still_penalized(self, adapter):
        m11 = M11Trademark(adapter)
        result = await m11.run({"sld": "disney", "words": ["disney"], "tld": "io", "word_count": 1})
        assert result.data["severity"] == "exact"
