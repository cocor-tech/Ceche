from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from ceche.domain.result import AppraisalResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    started_at      INTEGER NOT NULL,
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    total           INTEGER NOT NULL DEFAULT 0,
    succeeded       INTEGER NOT NULL DEFAULT 0,
    failed          INTEGER NOT NULL DEFAULT 0,
    fresh           INTEGER NOT NULL DEFAULT 0,
    version         TEXT NOT NULL DEFAULT '',
    command         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS appraisals (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    domain          TEXT NOT NULL,
    estimated_value REAL,
    range_low       REAL,
    range_high      REAL,
    confidence      TEXT,
    completeness    REAL,
    tld_score       REAL,
    weight_profile  TEXT,
    modules_json    TEXT NOT NULL DEFAULT '{}',
    error_type      TEXT,
    error_message   TEXT,
    created_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_appraisals_run ON appraisals(run_id);
CREATE INDEX IF NOT EXISTS idx_appraisals_domain ON appraisals(domain);
CREATE INDEX IF NOT EXISTS idx_appraisals_created ON appraisals(created_at);

CREATE TABLE IF NOT EXISTS ai_usage (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    module          TEXT NOT NULL,
    tokens_in       INTEGER NOT NULL DEFAULT 0,
    tokens_out      INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL NOT NULL DEFAULT 0.0,
    latency_ms      INTEGER NOT NULL DEFAULT 0,
    created_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_run ON ai_usage(run_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_provider ON ai_usage(provider);
"""


class AppraisalStore:
    """Persistent SQLite-backed storage for appraisal runs, results, and AI usage."""

    def __init__(self, db_path: str = "") -> None:
        if not db_path:
            home = Path.home() / ".config" / "ceche"
            home.mkdir(parents=True, exist_ok=True)
            db_path = str(home / "history.db")
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.executescript(_SCHEMA)
        conn.commit()
        conn.close()

    def record_run(
        self,
        domains: list[str],
        results: list[AppraisalResult],
        failures: list[dict[str, Any]],
        duration_ms: int = 0,
        fresh: bool = False,
        version: str = "",
        command: str = "",
    ) -> str:
        conn = sqlite3.connect(self._db_path)
        run_id = uuid.uuid4().hex[:12]
        now = int(time.time())
        total = len(domains)
        succeeded = len(results)
        failed = len(failures)
        conn.execute(
            "INSERT INTO runs (id, started_at, duration_ms, total, succeeded, failed, "
            "fresh, version, command) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, now, duration_ms, total, succeeded, failed,
             int(fresh), version, command),
        )
        for r in results:
            app_id = uuid.uuid4().hex[:12]
            conn.execute(
                "INSERT INTO appraisals (id, run_id, domain, estimated_value, "
                "range_low, range_high, confidence, completeness, tld_score, "
                "weight_profile, modules_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (app_id, run_id, r.domain, r.estimated_value,
                 r.range_low, r.range_high, r.confidence,
                 r.completeness_ratio, r.tld_score, r.weight_profile,
                 json.dumps(r.modules, default=str), now),
            )
        for f in failures:
            app_id = uuid.uuid4().hex[:12]
            conn.execute(
                "INSERT INTO appraisals (id, run_id, domain, error_type, "
                "error_message, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (app_id, run_id, f.get("domain", ""),
                 f.get("error_type", ""), f.get("error_message", ""), now),
            )
        conn.commit()
        conn.close()
        return run_id

    def list_runs(
        self, days: int = 30, command: str = "",
    ) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        since = int(time.time()) - days * 86400
        query = "SELECT * FROM runs WHERE started_at >= ?"
        params: list[Any] = [since]
        if command:
            query += " AND command = ?"
            params.append(command)
        query += " ORDER BY started_at DESC"
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        conn.close()
        return rows

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_domain_history(
        self, domain: str, days: int = 90,
    ) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        since = int(time.time()) - days * 86400
        rows = conn.execute(
            "SELECT * FROM appraisals WHERE domain = ? AND created_at >= ? "
            "ORDER BY created_at DESC",
            (domain.lower(), since),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_stats(self, days: int | None = None) -> dict[str, Any]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        since = int(time.time()) - (days * 86400) if days else 0
        time_filter = f"created_at >= {since}" if days else "1=1"
        total = conn.execute(
            f"SELECT COUNT(*) as c FROM appraisals WHERE {time_filter}",
        ).fetchone()["c"]
        with_value = conn.execute(
            f"SELECT COUNT(*) as c FROM appraisals "
            f"WHERE estimated_value IS NOT NULL AND {time_filter}",
        ).fetchone()["c"]
        avg_value = conn.execute(
            f"SELECT AVG(estimated_value) as v FROM appraisals "
            f"WHERE estimated_value IS NOT NULL AND {time_filter}",
        ).fetchone()["v"]
        conn.close()
        return {
            "total_appraisals": total,
            "with_value": with_value,
            "avg_estimated_value": round(avg_value, 2) if avg_value else None,
        }

    def get_ai_usage(
        self, days: int = 30, provider: str = "",
    ) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        since = int(time.time()) - days * 86400
        query = "SELECT * FROM ai_usage WHERE created_at >= ?"
        params: list[Any] = [since]
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        query += " ORDER BY created_at DESC"
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        conn.close()
        return rows

    def record_ai_usage(
        self,
        run_id: str,
        provider: str,
        model: str,
        module: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        latency_ms: int,
    ) -> str:
        conn = sqlite3.connect(self._db_path)
        uid = uuid.uuid4().hex[:12]
        now = int(time.time())
        conn.execute(
            "INSERT INTO ai_usage (id, run_id, provider, model, module, "
            "tokens_in, tokens_out, cost_usd, latency_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, run_id, provider, model, module,
             tokens_in, tokens_out, cost_usd, latency_ms, now),
        )
        conn.commit()
        conn.close()
        return uid

    def get_ai_usage_summary(
        self, days: int = 30,
    ) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        since = int(time.time()) - days * 86400
        rows = conn.execute(
            "SELECT provider, model, SUM(tokens_in) as tokens_in, "
            "SUM(tokens_out) as tokens_out, SUM(cost_usd) as cost_usd, "
            "COUNT(*) as calls, AVG(latency_ms) as avg_latency "
            "FROM ai_usage WHERE created_at >= ? "
            "GROUP BY provider, model ORDER BY cost_usd DESC",
            (since,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def clear(self, days: int | None = None) -> None:
        conn = sqlite3.connect(self._db_path)
        if days is not None:
            cutoff = int(time.time()) - days * 86400
            conn.execute("DELETE FROM ai_usage WHERE created_at < ?", (cutoff,))
            conn.execute("DELETE FROM appraisals WHERE created_at < ?", (cutoff,))
            conn.execute(
                "DELETE FROM runs WHERE started_at < ?", (cutoff,),
            )
        else:
            conn.executescript("DELETE FROM ai_usage; DELETE FROM appraisals; DELETE FROM runs;")
        conn.commit()
        conn.close()

    def export(self, path: str, days: int = 30) -> None:
        import json as _j
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        since = int(time.time()) - days * 86400
        runs = [dict(r) for r in conn.execute(
            "SELECT * FROM runs WHERE started_at >= ? ORDER BY started_at DESC",
            (since,),
        ).fetchall()]
        appraisals = [dict(r) for r in conn.execute(
            "SELECT * FROM appraisals WHERE created_at >= ? ORDER BY created_at DESC",
            (since,),
        ).fetchall()]
        conn.close()
        output = _j.dumps({"runs": runs, "appraisals": appraisals}, indent=2, default=str)
        Path(path).write_text(output)
