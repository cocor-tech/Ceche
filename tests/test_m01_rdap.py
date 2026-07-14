"""Tests for M1 — RDAP / WHOIS Lookup."""

from __future__ import annotations

import pytest

from ceche.domain import M1RDAP, ModuleStatus


@pytest.fixture
def mock_rdap_port():
    """Return a factory that creates mock RDAP adapters."""

    class _MockRDAP:
        def __init__(self, result: dict | None = None, error: Exception | None = None):
            self._result = result
            self._error = error

        async def lookup(self, domain: str) -> dict:
            if self._error:
                raise self._error
            if self._result:
                return self._result
            return {"_not_found": True, "domain": domain, "error_code": 404}

    return _MockRDAP


@pytest.fixture
def mock_cache():
    """Return a no-op cache that always calls the fn."""

    class _Cache:
        def __init__(self):
            self.stored: list[tuple[str, dict, int]] = []

        async def get(self, key: str) -> dict | None:
            return None

        async def set(self, key: str, value: dict, ttl: int) -> None:
            self.stored.append((key, value, ttl))

        async def get_or_compute(self, key: str, ttl: int, fn):
            result = await fn()
            await self.set(key, result, ttl)
            return result

    return _Cache()


def _rdap_json(
    domain: str,
    created: str,
    expired: str,
    registrar: str = "Test Registrar Inc.",
):
    return {
        "ldhName": domain,
        "events": [
            {"eventAction": "registration", "eventDate": created},
            {"eventAction": "expiration", "eventDate": expired},
            {"eventAction": "last changed", "eventDate": expired},
        ],
        "entities": [
            {
                "roles": ["registrar"],
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", registrar],
                    ],
                ],
            },
        ],
        "status": ["client delete prohibited", "client transfer prohibited"],
    }


AI_RDAP = "1997-01-01T05:00:00Z"
AI_RDAP_2030 = "2030-01-01T05:00:00Z"


class TestM1RDAP:
    async def test_registered_domain(self, mock_rdap_port, mock_cache):
        rdap = mock_rdap_port(
            result=_rdap_json("example.com", AI_RDAP, "2026-01-01T05:00:00Z"),
        )
        m1 = M1RDAP(rdap, mock_cache)
        result = await m1.run({"domain_name": "example.com"})

        assert result.status == ModuleStatus.SUCCESS
        assert result.value is not None
        assert result.confidence == 1.0
        assert result.module_name == "m1_rdap"

        data = result.data
        assert data["registered"] is True
        assert data["domain_name"] == "example.com"
        assert data["registrar"] == "Test Registrar Inc."

    async def test_unregistered_domain(self, mock_rdap_port, mock_cache):
        rdap = mock_rdap_port()
        m1 = M1RDAP(rdap, mock_cache)
        result = await m1.run({"domain_name": "nonexistent-test-xyz-123.com"})

        assert result.status == ModuleStatus.NOT_FOUND
        assert result.value is None
        assert result.data["registered"] is False

    async def test_age_multiplier_very_old(self, mock_rdap_port, mock_cache):
        rdap = mock_rdap_port(
            result=_rdap_json("old.com", "2000-01-01T00:00:00Z", AI_RDAP_2030),
        )
        m1 = M1RDAP(rdap, mock_cache)
        result = await m1.run({"domain_name": "old.com"})
        assert result.value == 3.0

    async def test_age_multiplier_moderate(self, mock_rdap_port, mock_cache):
        rdap = mock_rdap_port(
            result=_rdap_json("mid.com", "2015-06-01T00:00:00Z", AI_RDAP_2030),
        )
        m1 = M1RDAP(rdap, mock_cache)
        result = await m1.run({"domain_name": "mid.com"})
        assert result.value == 2.0

    async def test_age_multiplier_young(self, mock_rdap_port, mock_cache):
        rdap = mock_rdap_port(
            result=_rdap_json("young.com", "2024-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        m1 = M1RDAP(rdap, mock_cache)
        result = await m1.run({"domain_name": "young.com"})
        assert result.value in (1.0, 1.2)

    async def test_registrar_parsing(self, mock_rdap_port, mock_cache):
        rdap = mock_rdap_port(
            result=_rdap_json("foo.com", "2000-01-01T00:00:00Z", AI_RDAP_2030, "GoDaddy LLC"),
        )
        m1 = M1RDAP(rdap, mock_cache)
        result = await m1.run({"domain_name": "foo.com"})
        assert result.data["registrar"] == "GoDaddy LLC"

    async def test_no_domain_in_context(self, mock_rdap_port, mock_cache):
        rdap = mock_rdap_port()
        m1 = M1RDAP(rdap, mock_cache)
        result = await m1.run({})
        assert result.status == ModuleStatus.ERROR
        assert "no domain" in str(result.data.get("error", ""))

    async def test_rdap_error_returns_error_status(self, mock_rdap_port, mock_cache):
        rdap = mock_rdap_port(error=RuntimeError("connection refused"))
        m1 = M1RDAP(rdap, mock_cache)
        result = await m1.run({"domain_name": "error.com"})
        assert result.status == ModuleStatus.ERROR

    async def test_cache_is_used(self, mock_rdap_port):
        call_count = 0

        class _TrackingCache:
            async def get(self, key: str) -> dict | None:
                return None

            async def set(self, key: str, value: dict, ttl: int) -> None:
                pass

            async def get_or_compute(self, key: str, ttl: int, fn):
                nonlocal call_count
                call_count += 1
                return await fn()

        rdap = mock_rdap_port(
            result=_rdap_json("cached.com", "2000-01-01T00:00:00Z", AI_RDAP_2030),
        )
        m1 = M1RDAP(rdap, _TrackingCache())
        result1 = await m1.run({"domain_name": "cached.com"})
        result2 = await m1.run({"domain_name": "cached.com"})
        assert result1.status == ModuleStatus.SUCCESS
        assert result2.status == ModuleStatus.SUCCESS
        assert call_count == 2

    async def test_parse_no_events(self, mock_rdap_port, mock_cache):
        rdap = mock_rdap_port(result={"ldhName": "bare.com", "events": []})
        m1 = M1RDAP(rdap, mock_cache)
        result = await m1.run({"domain_name": "bare.com"})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["creation_date"] is None
        assert result.data["registrar"] is None

    async def test_parse_no_entities(self, mock_rdap_port, mock_cache):
        rdap = mock_rdap_port(result={
            "ldhName": "noentity.com",
            "events": [{"eventAction": "registration", "eventDate": "2010-01-01T00:00:00Z"}],
            "entities": [],
        })
        m1 = M1RDAP(rdap, mock_cache)
        result = await m1.run({"domain_name": "noentity.com"})
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["registrar"] is None
