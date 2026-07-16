from __future__ import annotations

from pathlib import Path
from typing import Any

import tomllib

_CONFIG_DIR = Path.home() / ".config" / "ceche"
_GLOBAL_PATH = _CONFIG_DIR / "config.toml"
_PROJECT_NAME = ".ceche.toml"


class ConfigStore:
    """Read/write TOML config files for the Ceche config system."""

    def __init__(self, project_dir: str | Path | None = None) -> None:
        self._project_path = (Path(project_dir or Path.cwd()) / _PROJECT_NAME).resolve()
        self._global_path = _GLOBAL_PATH
        self._global_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def project_path(self) -> Path:
        return self._project_path

    @property
    def global_path(self) -> Path:
        return self._global_path

    def read(self, path: Path | None = None, global_: bool = False) -> dict[str, Any]:
        target = path or (self._global_path if global_ else self._project_path)
        if not target.is_file():
            return {}
        return getattr(self, "_parse", lambda x: {})(target)  # backwards compat

    def read_flat(self, path: Path | None = None, global_: bool = False) -> dict[str, Any]:
        target = path or (self._global_path if global_ else self._project_path)
        if not target.is_file():
            return {}
        raw: dict[str, Any] = tomllib.loads(target.read_text())
        flat: dict[str, Any] = {}
        for section, values in raw.items():
            if isinstance(values, dict):
                for k, v in values.items():
                    flat[k] = v
            else:
                flat[section] = values
        return flat

    def write(
        self, config: dict[str, Any],
        path: Path | None = None, global_: bool = False,
    ) -> None:
        target = path or (self._global_path if global_ else self._project_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_format_toml(config))

    def set(self, key: str, value: str, global_: bool = False) -> Path:
        target = self._global_path if global_ else self._project_path
        target.parent.mkdir(parents=True, exist_ok=True)
        config = self.read_flat(target) if target.is_file() else {}
        config[key] = _coerce_type(key, value)
        target.write_text(_format_toml(config))
        return target

    def reset(self, global_: bool = False) -> None:
        target = self._global_path if global_ else self._project_path
        if target.is_file():
            target.unlink()

    def import_config(self, source: Path, global_: bool = False) -> Path:
        raw: dict[str, Any] = tomllib.loads(source.read_text())
        flat: dict[str, Any] = {}
        for section, values in raw.items():
            if isinstance(values, dict):
                for k, v in values.items():
                    flat[k] = v
            else:
                flat[section] = values
        target = self._global_path if global_ else self._project_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text())
        return target

    def export_config(self, path: Path, global_: bool = False) -> Path:
        source = self._global_path if global_ else self._project_path
        if not source.is_file():
            path.write_text("")
        else:
            path.write_text(source.read_text())
        return path

    def config_exists(self, global_: bool = False) -> bool:
        target = self._global_path if global_ else self._project_path
        return target.is_file()


def _format_toml(config: dict[str, Any]) -> str:
    lines: list[str] = []
    groups: dict[str, dict[str, Any]] = {"": {}}
    section_map = {
        "google_cse_key": "search", "google_cse_cx": "search", "brave_key": "search",
        "opr_key": "authority",
        "cache_path": "cache", "cache_enabled": "cache",
        "concurrency": "appraisal", "format": "appraisal", "fresh": "appraisal",
        "ai_enabled": "ai", "ai_temperature": "ai", "ai_max_tokens": "ai",
        "m6_max_tokens": "ai",
    }
    for k, v in config.items():
        sec = section_map.get(k, "")
        if sec not in groups:
            groups[sec] = {}
        groups[sec][k] = v
    for section in sorted(groups.keys()):
        entries = groups[section]
        if not entries:
            continue
        if section:
            lines.append(f"\n[{section}]")
        for k in sorted(entries.keys()):
            v = entries[k]
            if isinstance(v, bool):
                lines.append(f'{k} = {"true" if v else "false"}')
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
    return "\n".join(lines).strip() + "\n"


_TYPE_HINTS: dict[str, type] = {
    "concurrency": int,
    "fresh": bool,
    "cache_enabled": bool,
    "ai_enabled": bool,
    "ai_temperature": float,
    "ai_max_tokens": int,
    "m6_max_tokens": int,
}


def _coerce_type(key: str, value: str) -> int | float | bool | str:
    ctype = _TYPE_HINTS.get(key)
    if ctype is bool:
        return value.strip().lower() in ("true", "yes", "1")
    if ctype is int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    if ctype is float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    return value
