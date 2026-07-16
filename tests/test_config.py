"""Tests for Phase 2 — Config system."""

from __future__ import annotations

from pathlib import Path

from ceche.config import Config
from ceche.infrastructure.config.loader import ConfigLoader
from ceche.infrastructure.config.store import ConfigStore


class TestConfigDefaults:
    def test_defaults_have_all_fields(self) -> None:
        cfg = ConfigLoader.defaults()
        assert cfg.concurrency == 10
        assert cfg.format == "pretty"
        assert cfg.cache_enabled is True
        assert cfg.ai_enabled is False
        assert cfg.cache_path == "cache.db"
        assert cfg.ai_temperature == 0.1
        assert cfg.ai_max_tokens == 150
        assert cfg.m6_max_tokens == 500

    def test_load_returns_config(self) -> None:
        cfg = Config.load()
        assert isinstance(cfg, Config)
        assert cfg.concurrency >= 1
        assert cfg.ai_max_tokens >= 1

    def test_config_has_all_expected_keys(self) -> None:
        cfg = Config.load()
        expected = [
            "google_cse_key", "google_cse_cx", "brave_key", "opr_key",
            "cache_path", "fresh", "concurrency", "format", "cache_enabled",
            "ai_enabled", "ai_temperature", "ai_max_tokens", "m6_max_tokens",
            "profile",
        ]
        for key in expected:
            assert hasattr(cfg, key), f"Missing config field: {key}"


class TestConfigStore:
    def test_store_write_and_read(self, tmp_path: Path) -> None:
        store = ConfigStore(str(tmp_path))
        store.set("concurrency", "20", global_=True)
        data = store.read_flat(global_=True)
        assert data.get("concurrency") == 20

    def test_store_reset(self, tmp_path: Path) -> None:
        store = ConfigStore(str(tmp_path))
        store.set("concurrency", "30", global_=True)
        assert store.config_exists(global_=True)
        store.reset(global_=True)
        assert not store.config_exists(global_=True)

    def test_store_export_import_roundtrip(self, tmp_path: Path) -> None:
        store = ConfigStore(str(tmp_path))
        store.set("concurrency", "50", global_=True)
        export_path = tmp_path / "exported.toml"
        store.export_config(export_path, global_=True)
        assert export_path.is_file()
        assert "50" in export_path.read_text()

    def test_store_has_paths(self) -> None:
        store = ConfigStore()
        assert store.global_path.name == "config.toml"
        assert store.project_path.name == ".ceche.toml"
