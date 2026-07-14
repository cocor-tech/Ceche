"""Tests for M2 — TLD Score Table."""

from __future__ import annotations

import pytest

from ceche.domain import M2TLDTable, ModuleStatus


@pytest.fixture
def m2():
    return M2TLDTable()


class TestM2TLDTable:
    async def test_com_returns_10(self, m2):
        result = await m2.run({"tld": "com"})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["tld_score"] == 10.0
        assert result.data["weight_profile"] == "tier_10"

    async def test_net_returns_9(self, m2):
        result = await m2.run({"tld": "net"})
        assert result.data["tld_score"] == 9.0
        assert result.data["weight_profile"] == "tier_09"

    async def test_io_returns_8_5(self, m2):
        result = await m2.run({"tld": "io"})
        assert result.data["tld_score"] == 8.5
        assert result.data["weight_profile"] == "tier_085"

    async def test_ai_returns_8_5(self, m2):
        result = await m2.run({"tld": "ai"})
        assert result.data["tld_score"] == 8.5
        assert result.data["weight_profile"] == "tier_085"

    async def test_co_returns_8(self, m2):
        result = await m2.run({"tld": "co"})
        assert result.data["tld_score"] == 8.0
        assert result.data["weight_profile"] == "tier_08"

    async def test_icu_returns_1(self, m2):
        result = await m2.run({"tld": "icu"})
        assert result.data["tld_score"] == 1.0
        assert result.data["weight_profile"] == "tier_01"

    async def test_unknown_tld_returns_default(self, m2):
        result = await m2.run({"tld": "nonexistent"})
        assert result.data["tld_score"] == 0.2
        assert result.data["weight_profile"] == "tier_00"

    async def test_tld_is_case_insensitive(self, m2):
        r1 = await m2.run({"tld": "COM"})
        r2 = await m2.run({"tld": "Com"})
        r3 = await m2.run({"tld": "com"})
        assert r1.data["tld_score"] == 10.0
        assert r2.data["tld_score"] == 10.0
        assert r3.data["tld_score"] == 10.0

    async def test_tld_with_dot_prefix(self, m2):
        result = await m2.run({"tld": ".com"})
        assert result.data["tld_score"] == 10.0
        assert result.data["tld"] == "com"

    async def test_no_tld_in_context_returns_error(self, m2):
        result = await m2.run({})
        assert result.status == ModuleStatus.ERROR

    async def test_value_returns_score(self, m2):
        result = await m2.run({"tld": "com"})
        assert result.value == 10.0

    async def test_confidence_is_always_1(self, m2):
        result = await m2.run({"tld": "com"})
        assert result.confidence == 1.0

    async def test_data_contains_tier_label(self, m2):
        result = await m2.run({"tld": "com"})
        assert "tier_label" in result.data
        assert "Premium" in result.data["tier_label"]

    async def test_all_54_tlds_return_non_default(self, m2):
        known_tlds = [
            "com", "net", "io", "ai", "co", "de", "edu", "org", "xxx",
            "app", "it", "xyz", "us", "tv", "me", "cc", "to", "tech",
            "world", "eu", "sh", "ca", "inc", "wiki", "pro", "space",
            "shop", "online", "info", "in", "asia", "africa", "gg",
            "tel", "news", "site", "ltd", "cloud", "co.uk", "blog",
            "fun", "it.com", "sport", "studio", "live", "art",
            "network", "lgbt", "bio", "agency", "lol", "one", "biz", "icu",
        ]
        for tld in known_tlds:
            result = await m2.run({"tld": tld})
            assert result.data["tld_score"] != 0.2, f"{tld} should have custom score"
