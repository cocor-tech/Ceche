from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from ceche.domain.ports import CachePort

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    ttl         INTEGER NOT NULL,
    created_at  INTEGER NOT NULL,
    expires_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at);
"""

_CLEANUP_EVERY = 100


class SQLiteCacheAdapter(CachePort):
    def __init__(self, db_path: str = "cache.db") -> None:
        self._db_path = db_path
        self._write_count = 0
        self._init_db()

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.executescript(_SCHEMA)
        conn.execute("DELETE FROM cache WHERE expires_at < ?", (int(time.time()),))
        conn.commit()
        conn.close()

    async def get(self, key: str) -> dict[str, Any] | None:
        def _get() -> dict[str, Any] | None:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
            conn.close()
            if row is None:
                return None
            if row[1] < int(time.time()):
                self._delete_sync(key)
                return None
            return cast(dict[str, Any], json.loads(str(row[0])))

        return await asyncio.to_thread(_get)

    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        def _set() -> None:
            now = int(time.time())
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, ttl, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, json.dumps(value, default=str), ttl, now, now + ttl),
            )
            conn.commit()
            conn.close()

        await asyncio.to_thread(_set)

        self._write_count += 1
        if self._write_count % _CLEANUP_EVERY == 0:
            await self._cleanup()

    async def get_or_compute(
        self,
        key: str,
        ttl: int,
        fn: Callable[[], Any],
    ) -> dict[str, Any]:
        cached = await self.get(key)
        if cached is not None:
            return cached
        result = await fn()
        if isinstance(result, dict):
            await self.set(key, cast(dict[str, Any], result), ttl)
        return cast(dict[str, Any], result)

    async def _cleanup(self) -> None:
        def _do() -> None:
            conn = sqlite3.connect(self._db_path)
            conn.execute("DELETE FROM cache WHERE expires_at < ?", (int(time.time()),))
            conn.commit()
            conn.close()

        await asyncio.to_thread(_do)

    def _delete_sync(self, key: str) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        conn.commit()
        conn.close()
