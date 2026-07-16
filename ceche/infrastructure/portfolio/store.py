from __future__ import annotations

import csv
import io
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolios (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_domains (
    id              TEXT PRIMARY KEY,
    portfolio_id    TEXT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    domain          TEXT NOT NULL,
    added_at        INTEGER NOT NULL,
    tags            TEXT NOT NULL DEFAULT '[]',
    notes           TEXT NOT NULL DEFAULT '',
    estimated_value REAL,
    confidence      TEXT
);

CREATE INDEX IF NOT EXISTS idx_pd_portfolio ON portfolio_domains(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_pd_domain ON portfolio_domains(domain);
"""


class PortfolioStore:
    """SQLite-backed portfolio storage for domain collections."""

    def __init__(self, db_path: str = "") -> None:
        if not db_path:
            home = Path.home() / ".config" / "ceche"
            home.mkdir(parents=True, exist_ok=True)
            db_path = str(home / "portfolios.db")
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.executescript(_SCHEMA)
        conn.commit()
        conn.close()

    def create(self, name: str) -> dict[str, Any]:
        conn = sqlite3.connect(self._db_path)
        now = int(time.time())
        pid = uuid.uuid4().hex[:12]
        try:
            conn.execute(
                "INSERT INTO portfolios (id, name, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (pid, name, now, now),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Portfolio '{name}' already exists") from None
        conn.close()
        return {"id": pid, "name": name, "created_at": now}

    def list_all(self) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT p.*, COUNT(pd.id) as domain_count "
            "FROM portfolios p "
            "LEFT JOIN portfolio_domains pd ON pd.portfolio_id = p.id "
            "GROUP BY p.id ORDER BY p.name"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def show(self, name: str) -> dict[str, Any] | None:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM portfolios WHERE name = ?", (name,),
        ).fetchone()
        if row is None:
            conn.close()
            return None
        domains = conn.execute(
            "SELECT * FROM portfolio_domains WHERE portfolio_id = ? ORDER BY domain",
            (row["id"],),
        ).fetchall()
        conn.close()
        result = dict(row)
        result["domains"] = [dict(d) for d in domains]
        return result

    def delete(self, name: str) -> bool:
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT id FROM portfolios WHERE name = ?", (name,),
        ).fetchone()
        if row is None:
            conn.close()
            return False
        conn.execute("DELETE FROM portfolio_domains WHERE portfolio_id = ?", (row[0],))
        conn.execute("DELETE FROM portfolios WHERE id = ?", (row[0],))
        conn.commit()
        conn.close()
        return True

    def add(self, name: str, domains: list[str]) -> int:
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT id FROM portfolios WHERE name = ?", (name,),
        ).fetchone()
        if row is None:
            conn.close()
        pid = row[0]
        now = int(time.time())
        added = 0
        for d in domains:
            d = d.lower().strip()
            if not d:
                continue
            existing = conn.execute(
                "SELECT id FROM portfolio_domains WHERE portfolio_id = ? AND domain = ?",
                (pid, d),
            ).fetchone()
            if existing:
                continue
            did = uuid.uuid4().hex[:12]
            conn.execute(
                "INSERT INTO portfolio_domains (id, portfolio_id, domain, added_at) "
                "VALUES (?, ?, ?, ?)",
                (did, pid, d, now),
            )
            added += 1
        if added > 0:
            conn.execute(
                "UPDATE portfolios SET updated_at = ? WHERE id = ?",
                (now, pid),
            )
        conn.commit()
        conn.close()
        return added

    def remove(self, name: str, domains: list[str]) -> int:
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT id FROM portfolios WHERE name = ?", (name,),
        ).fetchone()
        if row is None:
            conn.close()
        pid = row[0]
        now = int(time.time())
        removed = 0
        for d in domains:
            d = d.lower().strip()
            if not d:
                continue
            cursor = conn.execute(
                "DELETE FROM portfolio_domains WHERE portfolio_id = ? AND domain = ?",
                (pid, d),
            )
            removed += cursor.rowcount
        if removed > 0:
            conn.execute(
                "UPDATE portfolios SET updated_at = ? WHERE id = ?",
                (now, pid),
            )
        conn.commit()
        conn.close()
        return removed

    def tag(self, name: str, domain: str, tag: str) -> bool:
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT pd.id, pd.tags FROM portfolio_domains pd "
            "JOIN portfolios p ON p.id = pd.portfolio_id "
            "WHERE p.name = ? AND pd.domain = ?",
            (name, domain.lower()),
        ).fetchone()
        if row is None:
            conn.close()
            return False
        did, tags_json = row[0], row[1]
        tags = json.loads(tags_json) if tags_json else []
        if tag not in tags:
            tags.append(tag)
        conn.execute(
            "UPDATE portfolio_domains SET tags = ? WHERE id = ?",
            (json.dumps(tags), did),
        )
        conn.commit()
        conn.close()
        return True

    def note(self, name: str, domain: str, note_text: str) -> bool:
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT pd.id FROM portfolio_domains pd "
            "JOIN portfolios p ON p.id = pd.portfolio_id "
            "WHERE p.name = ? AND pd.domain = ?",
            (name, domain.lower()),
        ).fetchone()
        if row is None:
            conn.close()
            return False
        conn.execute(
            "UPDATE portfolio_domains SET notes = ? WHERE id = ?",
            (note_text, row[0]),
        )
        conn.commit()
        conn.close()
        return True

    def search(self, query: str) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        like = f"%{query}%"
        rows = conn.execute(
            "SELECT pd.*, p.name as portfolio_name "
            "FROM portfolio_domains pd "
            "JOIN portfolios p ON p.id = pd.portfolio_id "
            "WHERE pd.domain LIKE ? "
            "OR pd.tags LIKE ? "
            "OR pd.notes LIKE ? "
            "ORDER BY pd.domain",
            (like, like, like),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_domain_value(
        self, portfolio: str, domain: str,
        estimated_value: float | None, confidence: str | None,
    ) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE portfolio_domains SET estimated_value = ?, confidence = ? "
            "WHERE domain = ? AND portfolio_id = (SELECT id FROM portfolios WHERE name = ?)",
            (estimated_value, confidence, domain, portfolio),
        )
        conn.commit()
        conn.close()

    def portfolio_exists(self, name: str) -> bool:
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT id FROM portfolios WHERE name = ?", (name,),
        ).fetchone()
        conn.close()
        return row is not None

    def export_csv(self, name: str) -> str:
        data = self.show(name)
        if not data:
            raise ValueError(f"Portfolio '{name}' not found")
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["domain", "added_at", "tags", "notes", "estimated_value", "confidence"])
        for d in data.get("domains", []):
            writer.writerow([
                d["domain"], d["added_at"], d["tags"],
                d["notes"], d.get("estimated_value"), d.get("confidence"),
            ])
        return buf.getvalue()

    def import_csv(self, name: str, csv_text: str) -> int:
        reader = csv.DictReader(io.StringIO(csv_text))
        domains: list[str] = []
        for row in reader:
            d = row.get("domain", "").strip().lower()
            if d:
                domains.append(d)
        return self.add(name, domains)
