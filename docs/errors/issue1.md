# Ceche — Full Issue Catalog

**63 issues identified.** Prioritized by severity with enterprise expected behavior for each.

---

## Tier 0: Critical (Blocks usage entirely)

| # | Issue | Expected Behavior After Fix |
|---|---|---|
| 1 | `textual` not in `pyproject.toml` | `pip install ceche[cli]` includes all CLI deps. `ceche start` works without extra steps. |
| 2 | `wordfreq` crashes at import if missing | Lazy import: `try: from wordfreq import word_frequency; except ImportError: word_frequency = lambda w, l: 0.0` — M6 gracefully degrades without `wordfreq`. |
| 3 | TUI command palette commands do nothing | Selecting a command from Ctrl+P executes the action (opens history, runs config, etc.). |

---

## Tier 1: Dependency & Install (Breaks pipx/CI)

| # | Issue | Expected Behavior |
|---|---|---|
| 4 | `all` extra doesn't include `tui` or `web` | `pip install ceche[all]` installs everything — CLI, web, M6, M7, TUI. Lock-step. |
| 5 | No lockfile (`requirements.txt`) | `requirements.txt` generated via `pip freeze` in CI. Reproducible builds guaranteed. |
| 6 | No lower bounds on key deps | `httpx>=0.27.0,<1.0`, `cryptography>=41.0.0,<44.0` — tested bounds prevent breaking changes. |
| 7 | `dev` extra missing `uvicorn`/`fastapi` | `pip install -e ".[dev]"` lets developers run every part of the system. |
| 8 | No `__main__.py` | `python -m ceche check example.com` works identically to `ceche check example.com`. |

---

## Tier 2: CLI Polish (User-facing daily friction)

| # | Issue | Expected Behavior |
|---|---|---|
| 9 | `--install-completion` / `--show-completion` in help | Output is clean. Only Ceche-specific options shown. Typer defaults suppressed. |
| 10 | `ceche check` has no description | `ceche check <domain>  Appraise a single domain`. Every command has a 1-line description. |
| 11 | `ceche ai key-list` not yet flattened | `ceche keys` lists keys. `ceche key add ...` adds. `ceche key remove <id>` removes. `ceche ai` is gone. |
| 12 | `ceche config profile` not yet flattened | `ceche profile new/show/list/use/remove` at top level. |
| 13 | No `--help` grouping | Commands grouped: **Appraisal** (check, bulk, compare, similar), **Data** (history, stats, portfolio), **Config** (config, cache, keys), **System** (server, version, start, watch, debug, demo). |
| 14 | Exit codes undocumented | `0` = success, `1` = partial failure (some domains failed), `2` = all failed, `3` = invalid input. Documented in `--help`. |
| 15 | No global `--json` / `--quiet` flags | `ceche --json check example.com` outputs JSON. `ceche --quiet check example.com` suppresses progress. Global flags work on every command. |
| 16 | `ceche appraise` hidden alias | `ceche appraise` shows deprecation warning: *"Use 'ceche check' instead"*, still works. |

---

## Tier 3: Error Handling (Production reliability)

| # | Issue | Expected Behavior |
|---|---|---|
| 17 | `_safe()` silently returns None on all errors | Errors are logged to stderr with module name + error type. Partial results still returned. |
| 18 | `bulk_engine.py` catches `Exception` bare | Catches specific exceptions per domain. Each failure is captured with phase, error type, and message. |
| 19 | Auto-logging swallows exceptions silently | Logs a warning to stderr: *"History save failed: <reason> — appraisal still completed."* |
| 20 | No user-visible error messages for cache failures | `ceche cache stats` shows last error timestamp and message. |
| 21 | AI provider errors return empty string | Router distinguishes: `"provider_unavailable"`, `"model_not_found"`, `"rate_limited"`, `"timeout"`. Each has a distinct return value. |
| 22 | `wordfreq` import at module level | Lazy import with clear error on first call if missing: *"Install wordfreq: pip install ceche[m6]"*. |

---

## Tier 4: Config & Documentation (Discoverability)

| # | Issue | Expected Behavior |
|---|---|---|
| 23 | Config file cascade undocumented | `ceche config path` shows cascade. `ceche --help` footer: *"Config: .ceche.toml → ~/.config/ceche/config.toml"*. |
| 24 | `ceche config import` validates nothing | Validates against schema. Prints field-specific errors: *"Unknown key 'foo' in [appraisal] section."* |
| 25 | `ceche config set` doesn't hint available keys | Invalid key prints: *"Unknown key. Available: concurrency, format, cache_enabled, ai_enabled..."* |
| 26 | No env vars documented in help | `ceche --help` ends with: *"Environment: CECHE_AI_ENABLED, CECHE_GOOGLE_CSE_KEY, ... See docs or 'ceche config' for all."* |
| 27 | No README update | README documents all 49 commands with examples. |
| 28 | No man page | `man ceche` shows full documentation. |
| 29 | No CHANGELOG | `CHANGELOG.md` lists every version with date and changes. |
| 30 | Stale docs (`bulk-upgrade.md`, etc.) | Only `README.md` and `CHANGELOG.md` exist. Planning docs removed from repo. |

---

## Tier 5: Security

| # | Issue | Expected Behavior |
|---|---|---|
| 31 | `vault.key` stored alongside `vault.db` | Vault encryption key derived from user password on first use. `vault.key` deleted. |
| 32 | Wayback uses plain HTTP | Wayback adapter uses `https://web.archive.org`. |
| 33 | No input sanitization on domains | Domains validated against RFC 1035 before appraisal. Invalid input returns clear error. |
| 34 | Dead security modules (`jwt`, `grants`, `audit`) | Either wired into the system or removed. No dead code. |
| 35 | `--dry-run` still imports real engine | `--dry-run` never makes network calls. Guaranteed offline. |

---

## Tier 6: Output Consistency

| # | Issue | Expected Behavior |
|---|---|---|
| 36 | `check --json` vs `bulk --json` different schemas | Both produce identical outer schema: `{version, generated_at, summary, results, failures}`. |
| 37 | `history --json` returns different shape than `stats` | All JSON output follows the same schema conventions. Field names consistent (`created_at` everywhere). |
| 38 | No JSON schema published | `ceche schema` prints JSON Schema for the output format. |
| 39 | CSV doesn't escape commas in domain names | All CSV values properly escaped/quoted per RFC 4180. |
| 40 | Module `status: "None"` possible | All module statuses are non-null strings: `"SUCCESS"`, `"SKIPPED"`, `"UNAVAILABLE"`, `"NOT_FOUND"`, `"ERROR"`. No `"None"`. |
| 41 | No `--pretty` default | Color output by default when stdout is a TTY. `--json` for machine-readable. |

---

## Tier 7: Testing & CI

| # | Issue | Expected Behavior |
|---|---|---|
| 42 | No CLI integration tests | `tests/test_cli.py` tests every command flag combination via `typer.testing.CliRunner`. |
| 43 | No test for `--version` | `ceche --version` tested in CI. |
| 44 | No test for command aliases | `ceche appraise` → `ceche check` alias tested. |
| 45 | No performance benchmarks | `ceche benchmark` measures and reports P50/P95/P99 latency. |
| 46 | No coverage measurement | CI enforces `>= 80%` coverage. Coverage report generated. |
| 47 | No GitHub Actions workflow | On push: lint → typecheck → test (all) → coverage. On tag: publish to PyPI + Docker. |

---

## Tier 8: TUI

| # | Issue | Expected Behavior |
|---|---|---|
| 48 | Sidebar empty on first launch | Shows "No recent appraisals" placeholder. |
| 49 | No loading indicator | Spinner or progress bar shown while appraisal runs. |
| 50 | Module table crashes on empty modules | Gracefully shows "No module data" row. |
| 51 | Command palette items don't execute | Each palette item maps to a real action. |
| 52 | Errors silently caught in TUI | Errors shown as toasts at the top of the screen. |
| 53 | No keyboard nav in module table | `j`/`k` scrolls table rows. Status bar shows binding. |
| 54 | No `--theme` flag | `ceche start --theme light` switches to light mode. |
| 55 | CSS inline in Python string | Extracted to `ceche/interfaces/tui/ceche.tcss`. Maintainable and overridable. |

---

## Tier 9: Infrastructure

| # | Issue | Expected Behavior |
|---|---|---|
| 56 | No GitHub Actions CI | Workflow runs on every push. Caches pip/tox. |
| 57 | No PyPI publishing | `git tag v2.1.0 && git push --tags` triggers publish workflow. |
| 58 | No Docker publishing | Tag push builds and pushes to `ghcr.io/cocor-tech/ceche`. |
| 59 | Dockerfile not multi-stage | Builder stage installs dev deps, runtime stage copies only installed package. Final image < 150MB. |
| 60 | No version bump script | `bumpver` or simple `python scripts/bump.py patch` reads and updates version in `pyproject.toml`. |

---

## Tier 10: Low Priority

| # | Issue | Expected Behavior |
|---|---|---|
| 61 | `ai_usage` table never written to | Either wired into AI router (records every AI call) or removed. |
| 62 | `_output_bulk_json` dead function | Removed. Dead code eliminated. |
| 63 | `ceche/vendor/textual/` doesn't exist | Vendoring is optional. Either vendor textual or document the dependency clearly. |

---

## Fix Order (4 Rounds)

| Round | What | Tiers | Commands Fixed | Est. Time |
|---|---|---|---|---|
| **1. Ship It** | T0 + T1 — make `ceche start` work, fix deps, lockfile | 0, 1 | `start`, `check`, `bulk`, all pipx installs | 1 session |
| **2. CLI Confidence** | T2 + T7 — rename commands, grouping, CLI tests, CI pipeline | 2, 7 | `keys`, `profile`, global `--json`, `--help` clean | 2 sessions |
| **3. Production Hardening** | T3 + T4 + T5 — error handling, config docs, security, env docs | 3, 4, 5 | All commands get better errors, `man` page, CHANGELOG | 2 sessions |
| **4. Polish** | T6 + T8 + T9 + T10 — output consistency, TUI, Docker, cleanup | 6, 8, 9, 10 | TUI toasts, `ceche schema`, CI/CD, dead code removal | 2 sessions |
