"""Tests for M9 — Search Results Checker."""

from __future__ import annotations

import pytest

from ceche.domain import M9SearchResults, ModuleStatus
from ceche.domain.modules.m09_search_results import _resolve_multiplier


class TestMultiplier:
    def test_above_10000(self):
        assert _resolve_multiplier(15000) == 5.0

    def test_above_1000(self):
        assert _resolve_multiplier(5000) == 3.0

    def test_above_100(self):
        assert _resolve_multiplier(500) == 2.0

    def test_above_10(self):
        assert _resolve_multiplier(50) == 1.3

    def test_below_10(self):
        assert _resolve_multiplier(5) == 1.0

    def test_zero(self):
        assert _resolve_multiplier(0) == 1.0


@pytest.fixture
def mock_primary():
    class _Mock:
        async def search(self, query: str):
            from ceche.domain.models import SearchResult
            return SearchResult(
                result_count=5000,
                snippets=["snippet1", "snippet2"],
                competing_tld=False,
            )
    return _Mock()


@pytest.fixture
def mock_backup():
    class _Mock:
        async def search(self, query: str):
            from ceche.domain.models import SearchResult
            return SearchResult(
                result_count=100,
                snippets=["brave1"],
                competing_tld=False,
            )
    return _Mock()


class TestM9SearchResults:
    async def test_successful_search(self, mock_primary):
        m9 = M9SearchResults(mock_primary)
        result = await m9.run({"domain_name": "example.com"})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["result_count"] == 5000
        assert result.data["multiplier"] == 3.0

    async def test_falls_back_to_backup(self, mock_backup):
        class _Failing:
            async def search(self, query: str):
                raise RuntimeError("fail")
        m9 = M9SearchResults(_Failing(), mock_backup)
        result = await m9.run({"domain_name": "example.com"})
        assert result.data["result_count"] == 100
        assert result.data["multiplier"] == 2.0

    async def test_no_results(self):
        class _NoResults:
            async def search(self, query: str):
                from ceche.domain.models import SearchResult
                return SearchResult(result_count=0, snippets=[], competing_tld=False)
        m9 = M9SearchResults(_NoResults())
        result = await m9.run({"domain_name": "fjfbfj.com"})
        assert result.data["result_count"] == 0
        assert result.data["multiplier"] == 1.0

    async def test_no_domain_returns_error(self, mock_primary):
        m9 = M9SearchResults(mock_primary)
        result = await m9.run({})
        assert result.status == ModuleStatus.ERROR

    async def test_value_matches_multiplier(self, mock_primary):
        m9 = M9SearchResults(mock_primary)
        result = await m9.run({"domain_name": "example.com"})
        assert result.value == 3.0
