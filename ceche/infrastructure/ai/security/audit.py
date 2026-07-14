from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init()

    def _init(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                action    TEXT    NOT NULL,
                actor     TEXT    NOT NULL,
                target    TEXT    NOT NULL,
                detail    TEXT    NOT NULL,
                success   INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor)")
        conn.commit()
        conn.close()

    def log(
        self,
        action: str,
        actor: str,
        target: str,
        detail: dict[str, Any] | None = None,
        success: bool = True,
    ) -> None:
        entry = {
            "timestamp": int(time.time()),
            "action": action,
            "actor": actor,
            "target": target,
            "detail": json.dumps(detail or {}),
            "success": 1 if success else 0,
        }
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO audit_log (timestamp, action, actor, target, detail, success) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entry["timestamp"], entry["action"], entry["actor"],
             entry["target"], entry["detail"], entry["success"]),
        )
        conn.commit()
        conn.close()

    def query(
        self,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        sql = "SELECT * FROM audit_log WHERE 1=1"
        params: list[Any] = []
        if actor:
            sql += " AND actor = ?"
            params.append(actor)
        if action:
            sql += " AND action = ?"
            params.append(action)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
