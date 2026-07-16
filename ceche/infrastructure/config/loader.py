from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import dotenv

from ceche.config import Config

_GLOBAL_CONFIG_DIR = Path.home() / ".config" / "ceche"
_GLOBAL_CONFIG_PATH = _GLOBAL_CONFIG_DIR / "config.toml"
_PROJECT_CONFIG_NAME = ".ceche.toml"


class ConfigLoader:
    """Load config from cascade: env vars > project .ceche.toml > global config.toml > defaults."""

    def __init__(self, project_dir: str | Path | None = None) -> None:
        dotenv.load_dotenv()
        self._project_path = (Path(project_dir or Path.cwd()) / _PROJECT_CONFIG_NAME).resolve()
        self._global_path = _GLOBAL_CONFIG_PATH

    def load(self) -> Config:
        merged = dict(self._defaults())
        self._merge(merged, self._read_toml(self._global_path))
        self._merge(merged, self._read_toml(self._project_path))
        self._merge(merged, self._from_env())
        return Config(**merged)

    @staticmethod
    def defaults() -> Config:
        return Config(**ConfigLoader._defaults())

    @staticmethod
    def _defaults() -> dict[str, Any]:
        return {
            "google_cse_key": "",
            "google_cse_cx": "",
            "brave_key": "",
            "opr_key": "",
            "cache_path": "cache.db",
            "fresh": False,
            "concurrency": 10,
            "format": "pretty",
            "cache_enabled": True,
            "ai_enabled": False,
            "ai_temperature": 0.1,
            "ai_max_tokens": 150,
        }

    @staticmethod
    def _read_toml(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        import tomllib
        raw: dict[str, Any] = tomllib.loads(path.read_text())
        flat: dict[str, Any] = {}
        for section, values in raw.items():
            if isinstance(values, dict):
                for k, v in values.items():
                    flat[k] = v
            else:
                flat[section] = values
        for key, ctype in _TYPE_HINTS.items():
            if key in flat and ctype is not str:
                try:
                    if ctype is bool:
                        if isinstance(flat[key], str):
                            flat[key] = flat[key].strip().lower() in ("true", "yes", "1")
                    elif ctype is int:
                        flat[key] = int(flat[key])
                    elif ctype is float:
                        flat[key] = float(flat[key])
                except (ValueError, TypeError):
                    pass
        return flat

    def _merge(self, target: dict[str, Any], source: dict[str, Any]) -> None:
        for k, v in source.items():
            if v is not None and v != "":
                target[k] = v

    @staticmethod
    def _from_env() -> dict[str, Any]:
        env: dict[str, Any] = {}
        mappings = {
            "CECHE_GOOGLE_CSE_KEY": "google_cse_key",
            "CECHE_GOOGLE_CSE_CX": "google_cse_cx",
            "CECHE_BRAVE_KEY": "brave_key",
            "CECHE_OPR_KEY": "opr_key",
            "CECHE_CACHE_PATH": "cache_path",
            "CECHE_CONCURRENCY": "concurrency",
            "CECHE_FORMAT": "format",
            "CECHE_AI_ENABLED": "ai_enabled",
            "CECHE_FRESH": "fresh",
            "CECHE_AI_TEMPERATURE": "ai_temperature",
            "CECHE_AI_MAX_TOKENS": "ai_max_tokens",
            "CECHE_CACHE_ENABLED": "cache_enabled",
        }
        for env_key, config_key in mappings.items():
            val = os.getenv(env_key)
            if val is not None:
                ctype = _TYPE_HINTS.get(config_key)
                if ctype is bool:
                    env[config_key] = val.strip().lower() in ("1", "true", "yes")
                elif ctype is int:
                    try:
                        env[config_key] = int(val)
                    except (ValueError, TypeError):
                        pass
                elif ctype is float:
                    try:
                        env[config_key] = float(val)
                    except (ValueError, TypeError):
                        pass
                else:
                    env[config_key] = val
        return env


_TYPE_HINTS: dict[str, type] = {
    "concurrency": int,
    "fresh": bool,
    "cache_enabled": bool,
    "ai_enabled": bool,
    "ai_temperature": float,
    "ai_max_tokens": int,
}
