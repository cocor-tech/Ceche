from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class AIAuditLogger:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init()

    def _init(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_audit (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     INTEGER NOT NULL,
                domain        TEXT    NOT NULL,
                module        TEXT    NOT NULL,
                prompt_id     TEXT    NOT NULL,
                prompt_version TEXT   NOT NULL,
                provider      TEXT    NOT NULL,
                model         TEXT    NOT NULL,
                prompt_text   TEXT    NOT NULL,
                response_text TEXT    NOT NULL,
                tools_called  TEXT    NOT NULL DEFAULT '[]',
                tool_results  TEXT    NOT NULL DEFAULT '[]',
                latency_ms    INTEGER NOT NULL,
                tokens_in     INTEGER NOT NULL DEFAULT 0,
                tokens_out    INTEGER NOT NULL DEFAULT 0,
                cost_usd      REAL    NOT NULL DEFAULT 0.0,
                success       INTEGER NOT NULL,
                error_detail  TEXT,
                original_value TEXT,
                blended_value TEXT,
                blending_weight REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_time ON ai_audit(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_module ON ai_audit(module)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_domain ON ai_audit(domain)")
        conn.commit()
        conn.close()

    def log(
        self,
        domain: str,
        module: str,
        prompt_id: str,
        prompt_version: str,
        provider: str,
        model: str,
        prompt_text: str,
        response_text: str,
        tools_called: list[str] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        latency_ms: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        success: bool = True,
        error_detail: str | None = None,
        original_value: str | None = None,
        blended_value: str | None = None,
        blending_weight: float | None = None,
    ) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO ai_audit (timestamp, domain, module, prompt_id, "
            "prompt_version, provider, model, prompt_text, response_text, "
            "tools_called, tool_results, latency_ms, tokens_in, tokens_out, "
            "cost_usd, success, error_detail, original_value, blended_value, "
            "blending_weight) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(time.time() * 1000), domain, module, prompt_id,
                prompt_version, provider, model,
                prompt_text[:200], response_text[:200],
                json.dumps(tools_called or []),
                json.dumps(tool_results or []),
                latency_ms, tokens_in, tokens_out, cost_usd,
                1 if success else 0, error_detail,
                original_value, blended_value, blending_weight,
            ),
        )
        conn.commit()
        conn.close()

    def query(
        self, domain: str | None = None, module: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        sql = "SELECT * FROM ai_audit WHERE 1=1"
        params: list[Any] = []
        if domain:
            sql += " AND domain = ?"
            params.append(domain)
        if module:
            sql += " AND module = ?"
            params.append(module)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        conn = sqlite3.connect(self._db_path)
        total = conn.execute("SELECT COUNT(*) FROM ai_audit").fetchone()
        success = conn.execute(
            "SELECT COUNT(*) FROM ai_audit WHERE success = 1"
        ).fetchone()
        avg_lat = conn.execute(
            "SELECT AVG(latency_ms) FROM ai_audit WHERE success = 1"
        ).fetchone()
        total_cost = conn.execute(
            "SELECT SUM(cost_usd) FROM ai_audit"
        ).fetchone()
        conn.close()
        return {
            "total_calls": total[0] if total else 0,
            "successes": success[0] if success else 0,
            "avg_latency_ms": round(avg_lat[0], 1) if avg_lat and avg_lat[0] else 0,
            "total_cost_usd": round(total_cost[0], 4) if total_cost and total_cost[0] else 0.0,
        }
