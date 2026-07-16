"""Tests for Phase 5 — Portfolio system."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceche.infrastructure.portfolio.store import PortfolioStore


class TestPortfolioStore:
    def test_create_and_list(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        portfolios = store.list_all()
        assert len(portfolios) == 1
        assert portfolios[0]["name"] == "test"

    def test_create_duplicate_raises(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        try:
            store.create("test")
            pytest.fail("should have raised")
        except ValueError:
            pass

    def test_show_returns_portfolio_with_domains(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        store.add("test", ["a.com", "b.com"])
        data = store.show("test")
        assert data is not None
        assert data["name"] == "test"
        assert len(data["domains"]) == 2

    def test_show_nonexistent(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        assert store.show("nonexistent") is None

    def test_delete(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        assert store.delete("test") is True
        assert store.show("test") is None

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        assert store.delete("test") is False

    def test_add_domains(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        added = store.add("test", ["a.com", "b.com", "a.com"])
        assert added == 2  # dedup
        data = store.show("test")
        assert len(data["domains"]) == 2

    def test_remove_domains(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        store.add("test", ["a.com", "b.com", "c.com"])
        removed = store.remove("test", ["a.com", "c.com"])
        assert removed == 2
        data = store.show("test")
        assert len(data["domains"]) == 1
        assert data["domains"][0]["domain"] == "b.com"

    def test_tag_domain(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        store.add("test", ["a.com"])
        assert store.tag("test", "a.com", "high-value") is True
        assert store.tag("test", "a.com", "high-value") is True  # idempotent
        # verify tag was saved
        data = store.show("test")
        import json
        tags = json.loads(data["domains"][0]["tags"])
        assert "high-value" in tags

    def test_note_domain(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        store.add("test", ["a.com"])
        assert store.note("test", "a.com", "my note") is True
        data = store.show("test")
        assert data["domains"][0]["notes"] == "my note"

    def test_search(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("p1")
        store.add("p1", ["example.com", "test.io"])
        store.create("p2")
        store.add("p2", ["example.org"])
        results = store.search("example")
        assert len(results) == 2

    def test_update_domain_value(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        store.add("test", ["a.com"])
        store.update_domain_value("test", "a.com", 5000.0, "medium")
        data = store.show("test")
        assert data["domains"][0]["estimated_value"] == 5000.0

    def test_portfolio_exists(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        assert store.portfolio_exists("test") is False
        store.create("test")
        assert store.portfolio_exists("test") is True

    def test_export_csv(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        store.add("test", ["a.com", "b.com"])
        csv_text = store.export_csv("test")
        assert "a.com" in csv_text
        assert "b.com" in csv_text
        assert csv_text.count("\n") >= 3  # header + 2 domains

    def test_import_csv(self, tmp_path: Path) -> None:
        store = PortfolioStore(str(tmp_path / "pf.db"))
        store.create("test")
        csv_text = "domain\na.com\nb.com\n"
        added = store.import_csv("test", csv_text)
        assert added == 2
        data = store.show("test")
        assert len(data["domains"]) == 2
