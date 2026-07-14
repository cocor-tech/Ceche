"""Tests for M14 — SQLite Cache Layer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ceche.infrastructure.cache.sqlite_adapter import SQLiteCacheAdapter


@pytest.fixture
def cache():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        c = SQLiteCacheAdapter(db_path)
        yield c


class TestSQLiteCache:
    async def test_set_and_get(self, cache):
        await cache.set("test:key1", {"value": 42}, 3600)
        result = await cache.get("test:key1")
        assert result is not None
        assert result["value"] == 42

    async def test_get_missing_key(self, cache):
        result = await cache.get("nonexistent")
        assert result is None

    async def test_overwrite_key(self, cache):
        await cache.set("test:key1", {"a": 1}, 3600)
        await cache.set("test:key1", {"b": 2}, 3600)
        result = await cache.get("test:key1")
        assert result == {"b": 2}

    async def test_expired_key(self, cache):
        await cache.set("test:expiring", {"x": 1}, ttl=-1)
        result = await cache.get("test:expiring")
        assert result is None

    async def test_get_or_compute_cache_hit(self, cache):
        await cache.set("test:hit", {"cached": True}, 3600)
        call_count = 0

        async def fn():
            nonlocal call_count
            call_count += 1
            return {"fresh": True}

        result = await cache.get_or_compute("test:hit", 3600, fn)
        assert result["cached"] is True
        assert call_count == 0

    async def test_get_or_compute_cache_miss(self, cache):
        call_count = 0

        async def fn():
            nonlocal call_count
            call_count += 1
            return {"computed": True}

        result = await cache.get_or_compute("test:miss", 3600, fn)
        assert result["computed"] is True
        assert call_count == 1

    async def test_get_or_compute_writes_to_cache(self, cache):
        call_count = 0

        async def fn():
            nonlocal call_count
            call_count += 1
            return {"value": 99}

        result1 = await cache.get_or_compute("test:write", 3600, fn)
        result2 = await cache.get_or_compute("test:write", 3600, fn)
        assert result1["value"] == 99
        assert result2["value"] == 99
        assert call_count == 1

    async def test_multiple_keys(self, cache):
        await cache.set("k1", {"n": 1}, 3600)
        await cache.set("k2", {"n": 2}, 3600)
        await cache.set("k3", {"n": 3}, 3600)

        r1 = await cache.get("k1")
        r2 = await cache.get("k2")
        r3 = await cache.get("k3")

        assert r1["n"] == 1
        assert r2["n"] == 2
        assert r3["n"] == 3

    async def test_persistence_across_instances(self, cache):
        await cache.set("persist:key", {"hello": "world"}, 3600)

        db = cache._db_path
        cache2 = SQLiteCacheAdapter(db)
        result = await cache2.get("persist:key")
        assert result == {"hello": "world"}
