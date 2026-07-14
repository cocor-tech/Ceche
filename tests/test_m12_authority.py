"""Tests for M12 — Dynamic Authority (updated)."""

from __future__ import annotations

from ceche.domain import M12Authority, ModuleStatus
from ceche.domain.modules.m12_authority import _dynamic_blend


class _Wayback:
    async def get_snapshots(self, domain: str):
        return {"count": 500, "first_date": "2010-01-01"}


class _Ahrefs:
    def __init__(self, dr: float | None = 45.0):
        self._dr = dr

    async def lookup(self, domain: str):
        return self._dr


class _OPR:
    def __init__(self, score: float | None = 6.5):
        self._score = score

    async def lookup(self, domain: str):
        return {"rank": 50000, "score": self._score, "ref_domains": 1200}


class _FailingAhrefs:
    async def lookup(self, domain: str):
        raise RuntimeError("fail")


class _FailingOPR:
    async def lookup(self, domain: str):
        raise RuntimeError("fail")


class TestDynamicBlend:
    def test_three_sources(self):
        result = _dynamic_blend(45.0, 6.5, 500)
        assert result is not None
        assert 0.4 <= result <= 0.7

    def test_ahrefs_only(self):
        result = _dynamic_blend(45.0, None, 500)
        assert result is not None

    def test_opr_only(self):
        result = _dynamic_blend(None, 6.5, 500)
        assert result is not None

    def test_wayback_only(self):
        result = _dynamic_blend(None, None, 500)
        assert result is not None
        assert result == 0.7  # snapshot_score(500) = 0.7

    def test_all_null(self):
        result = _dynamic_blend(None, None, 0)
        assert result is not None
        assert result == 0.0  # snapshot_score(0) = 0.0


class TestM12Dynamic:
    async def test_all_three_adapters(self):
        wb = _Wayback()
        ah = _Ahrefs(45.0)
        op = _OPR(6.5)
        m12 = M12Authority(wb, ah, op)
        result = await m12.run({
            "domain_name": "example.com", "registered": True, "age_years": 10.0,
        })
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["ahrefs_dr"] == 45.0
        assert result.data["opr_score"] == 6.5
        assert result.data["sources_active"] >= 3

    async def test_wayback_only(self):
        wb = _Wayback()
        m12 = M12Authority(wb)
        result = await m12.run({
            "domain_name": "example.com", "registered": True, "age_years": 10.0,
        })
        assert result.status == ModuleStatus.SUCCESS
        assert result.data["ahrefs_dr"] is None
        assert result.data["opr_score"] is None
        assert result.data["authority"] is not None

    async def test_wayback_plus_ahrefs(self):
        m12 = M12Authority(_Wayback(), _Ahrefs(45.0))
        result = await m12.run({
            "domain_name": "example.com", "registered": True, "age_years": 10.0,
        })
        assert result.data["ahrefs_dr"] == 45.0
        assert result.data["sources_active"] >= 2

    async def test_adapter_failure_graceful(self):
        m12 = M12Authority(_Wayback(), _FailingAhrefs(), _FailingOPR())
        result = await m12.run({
            "domain_name": "example.com", "registered": True, "age_years": 10.0,
        })
        assert result.data["ahrefs_dr"] is None
        assert result.data["opr_score"] is None

    async def test_unregistered_skipped(self):
        m12 = M12Authority(_Wayback(), _Ahrefs(), _OPR())
        result = await m12.run({
            "domain_name": "example.com", "registered": False,
        })
        assert result.status == ModuleStatus.SKIPPED

    async def test_data_contains_all_fields(self):
        m12 = M12Authority(_Wayback(), _Ahrefs(), _OPR())
        result = await m12.run({
            "domain_name": "example.com", "registered": True, "age_years": 5.0,
        })
        for key in ("ahrefs_dr", "opr_score", "snapshots", "parked", "authority", "multiplier", "sources_active", "sources_total"):
            assert key in result.data, f"missing field: {key}"
