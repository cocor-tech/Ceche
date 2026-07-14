"""Tests for M17 — Engine Orchestrator."""

from __future__ import annotations

from ceche.engine import AppraisalEngine


class _MockRDAP:
    def __init__(self, registered: bool = True) -> None:
        self._registered = registered

    async def lookup(self, domain: str) -> dict:
        if self._registered:
            return {
                "ldhName": domain,
                "events": [
                    {"eventAction": "registration", "eventDate": "2000-01-01T00:00:00Z"},
                    {"eventAction": "expiration", "eventDate": "2030-01-01T00:00:00Z"},
                ],
                "entities": [],
            }
        return {"_not_found": True}

    async def get(self, key: str) -> dict | None:
        return None

    async def set(self, key: str, value: dict, ttl: int) -> None:
        pass

    async def get_or_compute(self, key: str, ttl: int, fn):
        return await fn()


class _MockCache:
    async def get(self, key: str) -> dict | None:
        return None

    async def set(self, key: str, value: dict, ttl: int) -> None:
        pass

    async def get_or_compute(self, key: str, ttl: int, fn):
        return await fn()


class _MockKeyword:
    async def get_popularity(self, term: str) -> float:
        _map: dict[str, float] = {"car": 80.0, "go": 60.0, "daddy": 20.0}
        return _map.get(term, 0.0)


class _MockTrademark:
    async def check(self, term: str) -> object:
        from ceche.domain.models import TrademarkResult
        return TrademarkResult(conflict=False, severity="none", marks=[])


class _MockWayback:
    async def get_snapshots(self, domain: str) -> dict:
        return {"count": 500, "first_date": "2010-01-01"}


class _MockAhrefs:
    async def lookup(self, domain: str) -> float | None:
        return 45.0


class _MockOPR:
    async def lookup(self, domain: str) -> dict:
        return {"rank": 50000, "score": 6.5, "ref_domains": 1200}


def _build_engine(registered: bool = True):
    return AppraisalEngine(
        rdap=_MockRDAP(registered=registered),  # type: ignore[arg-type]
        cache=_MockCache(),  # type: ignore[arg-type]
        keyword=_MockKeyword(),  # type: ignore[arg-type]
        trademark=_MockTrademark(),  # type: ignore[arg-type]
        wayback=_MockWayback(),  # type: ignore[arg-type]
        ahrefs=_MockAhrefs(),  # type: ignore[arg-type]
        opr=_MockOPR(),  # type: ignore[arg-type]
    )


class TestAppraisalEngine:
    async def test_appraises_registered_com(self):
        engine = _build_engine(registered=True)
        result = await engine.appraise("car.com")
        assert result.estimated_value is not None
        assert result.estimated_value > 1_000_000
        assert result.weight_profile is not None

    async def test_appraises_unregistered_domain(self):
        engine = _build_engine(registered=False)
        result = await engine.appraise("sadmecry.com")
        assert result.estimated_value is not None
        assert result.completeness_ratio is not None

    async def test_appraises_brandable(self):
        engine = _build_engine(registered=False)
        result = await engine.appraise("nekwasa.com")
        assert result.estimated_value is not None

    async def test_output_has_domain(self):
        engine = _build_engine()
        result = await engine.appraise("example.com")
        assert result.domain == "example.com"

    async def test_output_has_modules(self):
        engine = _build_engine()
        result = await engine.appraise("example.com")
        assert len(result.modules) > 5

    async def test_range_high_above_low(self):
        engine = _build_engine()
        result = await engine.appraise("example.com")
        if result.range_low and result.range_high:
            assert result.range_high >= result.range_low

    async def test_car_com_valuation(self):
        engine = _build_engine(registered=True)
        result = await engine.appraise("car.com")
        assert result.estimated_value is not None
        assert result.estimated_value > 500_000
