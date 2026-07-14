"""Tests for M10 — Cross-TLD Check."""

from __future__ import annotations

import pytest

from ceche.domain import M10CrossTLD, ModuleStatus


@pytest.fixture
def mock_rdap():
    class _MockRDAP:
        def __init__(self, registered_tlds: set[str] | None = None) -> None:
            self._registered = registered_tlds or set()

        async def lookup(self, domain: str) -> dict:
            tld = domain.rsplit(".", 1)[-1]
            if tld in self._registered:
                return {
                    "ldhName": domain,
                    "events": [
                        {"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"},
                    ],
                    "entities": [],
                }
            return {"_not_found": True, "domain": domain}

    return _MockRDAP


class TestM10CrossTLD:
    async def test_dot_com_no_penalty(self, mock_rdap):
        rdap = mock_rdap(registered_tlds={"com"})
        m10 = M10CrossTLD(rdap)
        result = await m10.run({"domain_name": "example.com", "tld": "com"})
        assert result.data["multiplier"] == 1.0
        assert result.data["is_com"] is True

    async def test_non_dot_com_with_com_active(self, mock_rdap):
        rdap = mock_rdap(registered_tlds={"com"})
        m10 = M10CrossTLD(rdap)
        result = await m10.run({"domain_name": "example.io", "tld": "io"})
        assert result.data["multiplier"] == 0.5
        assert result.data["com_active"] is True

    async def test_non_dot_com_without_com_variant(self, mock_rdap):
        rdap = mock_rdap()
        m10 = M10CrossTLD(rdap)
        result = await m10.run({"domain_name": "example.io", "tld": "io"})
        assert result.data["multiplier"] == 1.0
        assert result.data["com_active"] is False

    async def test_no_domain_returns_error(self, mock_rdap):
        rdap = mock_rdap()
        m10 = M10CrossTLD(rdap)
        result = await m10.run({})
        assert result.status == ModuleStatus.ERROR

    async def test_value_is_multiplier(self, mock_rdap):
        rdap = mock_rdap(registered_tlds={"com"})
        m10 = M10CrossTLD(rdap)
        result = await m10.run({"domain_name": "example.io", "tld": "io"})
        assert result.value == 0.5

    async def test_variants_recorded(self, mock_rdap):
        rdap = mock_rdap(registered_tlds={"com", "net", "org"})
        m10 = M10CrossTLD(rdap)
        result = await m10.run({"domain_name": "example.io", "tld": "io"})
        assert "com" in result.data["variants"]
        assert "net" in result.data["variants"]
        assert "org" in result.data["variants"]
