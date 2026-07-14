"""Tests for M12 — Backlink / History / Age Checker."""

from __future__ import annotations

import pytest

from ceche.domain import M12Authority, ModuleStatus
from ceche.domain.modules.m12_authority import _authority_multiplier, _blend_authority
from ceche.infrastructure.authority.wayback_adapter import WaybackAdapter


@pytest.fixture
def wayback():
    class _Mock:
        async def get_snapshots(self, domain: str):
            return {"count": 500, "first_date": "2010-01-01"}
    return _Mock()


@pytest.fixture
def ahrefs():
    class _Mock:
        async def lookup(self, domain: str):
            return 45.0
    return _Mock()


@pytest.fixture
def opr():
    class _Mock:
        async def lookup(self, domain: str):
            return {"rank": 50000, "score": 6.5, "ref_domains": 1200}
    return _Mock()


@pytest.fixture
def m12(wayback, ahrefs, opr):
    return M12Authority(wayback, ahrefs, opr)


class TestBlendAuthority:
    def test_both_available(self):
        result = _blend_authority(45.0, 6.5)
        assert result == pytest.approx(0.53, rel=0.1)

    def test_ahrefs_only(self):
        result = _blend_authority(45.0, None)
        assert result == pytest.approx(0.36, rel=0.1)

    def test_opr_only(self):
        result = _blend_authority(None, 6.5)
        assert result == pytest.approx(0.52, rel=0.1)

    def test_neither(self):
        assert _blend_authority(None, None) is None


class TestAuthorityMultiplier:
    def test_high_authority(self):
        assert _authority_multiplier(0.95, False) == 3.0

    def test_medium_authority(self):
        assert _authority_multiplier(0.55, False) == 2.0

    def test_low_authority(self):
        assert _authority_multiplier(0.30, False) == 1.2

    def test_very_low(self):
        assert _authority_multiplier(0.10, False) == 1.0

    def test_parked_caps_at_half(self):
        assert _authority_multiplier(0.95, True) == 0.5


class TestWayback:
    def test_parked_flag_with_snapshots(self):
        assert WaybackAdapter.parked_flag(10, 5.0) is False

    def test_parked_flag_zero_snapshots(self):
        assert WaybackAdapter.parked_flag(0, 5.0) is True

    def test_parked_flag_young_domain_exempt(self):
        assert WaybackAdapter.parked_flag(0, 0.3) is False

    def test_history_multiplier_established(self):
        assert WaybackAdapter.history_multiplier(5000) == 3.0

    def test_history_multiplier_none(self):
        assert WaybackAdapter.history_multiplier(0) == 0.5


class TestM12Authority:
    async def test_registered_domain(self, m12):
        result = await m12.run({
            "domain_name": "example.com", "registered": True, "age_years": 10.0,
        })
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["authority"] is not None
        assert result.data["multiplier"] >= 1.2

    async def test_unregistered_skipped(self, m12):
        result = await m12.run({
            "domain_name": "example.com", "registered": False, "age_years": None,
        })
        assert result.status == ModuleStatus.SKIPPED
        assert result.value is None

    async def test_no_domain_error(self, m12):
        result = await m12.run({"registered": True})
        assert result.status == ModuleStatus.ERROR

    async def test_parked_domain_capped(self, wayback, ahrefs, opr):
        class _ParkedWayback:
            async def get_snapshots(self, domain: str):
                return {"count": 0}
        m12 = M12Authority(_ParkedWayback(), ahrefs, opr)
        result = await m12.run({
            "domain_name": "example.com", "registered": True, "age_years": 5.0,
        })
        assert result.data["parked"] is True
        assert result.data["multiplier"] <= 0.5
