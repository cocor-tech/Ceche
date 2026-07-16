# Ceche Command Build Plan

7 phases. Each phase produces working, shippable increments. No phase depends on a later phase to compile.

---

## Dependency Graph

```
Phase 1: Output Cleanup
    │
    ▼
Phase 2: Config System
    │
    ▼
Phase 3: Output Engine (formats, filter, sort, file output)
    │
    ├──────────────────┐
    ▼                  ▼
Phase 4: Persistence    Phase 5: Portfolios
(history, stats, cache)
    │                    │
    └────────┬───────────┘
             ▼
       Phase 6: Serve + Web + TUI
             │
             ▼
       Phase 7: Advanced
       (watch, schedule, compare, diff, similar, plugins, deploy)
```

---

## Phase 1: Engine Output Cleanup

**Goal:** Fix output bugs, unify schema. Foundation for everything else.

**Duration:** 1 session
**New files:** 1
**Modified files:** 5
**Net commands gained:** 0 (quality fix)

### Step 1.1: Fix `_module_breakdown` status field

**File:** `ceche/engine.py:238-255`

Current:
```python
entry["status"] = str(raw.get("status"))   # → "None" for 13/14 modules
```

Change to:
```python
ms = raw.pop("_module_status", "")
entry["status"] = ms.replace("ModuleStatus.", "") if ms else ""
if name == "m6_segmenter" and "status" in entry:
    entry["result"] = entry.pop("status")
```

### Step 1.2: Always fill all 14 module slots

**File:** `ceche/engine.py:238-255`

Add slots for modules that were never instantiated (adapter not configured):
```python
_MODULE_NAMES = [
    "m1_rdap", "m2_tld_table", "m3_length", "m4_word_count",
    "m5_pronounceability", "m6_segmenter", "m7_keyword_popularity",
    "m8_cpc", "m9_search_results", "m10_cross_tld",
    "m11_trademark", "m12_authority", "m13_confidence",
    "m15_pricing", "m16_brandability",
]

def _module_breakdown(self, ctx):
    for name in _MODULE_NAMES:
        raw = ctx.get(f"result_{name}")
        if raw is None:
            # Module was never run — adapter not configured
            entry = {"status": "UNAVAILABLE", "reason": "No adapter configured"}
        elif isinstance(raw, dict):
            entry = dict(raw)
            ...
        breakdown[name] = entry
```

### Step 1.3: Add `version` + `generated_at` to `AppraisalResult`

**File:** `ceche/domain/result.py`

```python
@dataclass
class AppraisalResult:
    domain: str
    estimated_value: float | None
    range_low: float | None
    range_high: float | None
    confidence: str | None
    completeness_ratio: float | None
    tld_score: float | None
    weight_profile: str | None
    modules: dict[str, dict[str, Any]] = field(default_factory=dict)
    version: str = ""                    # new
    generated_at: str = ""               # new
```

Populated in `engine.appraise()`:
```python
import datetime as _dt
import importlib.metadata as _im

result = AppraisalResult(
    ...
    version=_im.version("ceche"),
    generated_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
)
```

### Step 1.4: Restructure M15 `breakdown`

**File:** `ceche/domain/modules/m15_pricing.py`

New dataclass:
```python
@dataclass
class BreakdownEntry:
    multiplier: float | None
    weight: float | None
    contribution: float | None
    effect: str           # boost, penalty, neutral, unavailable
    impact: float         # Percentage impact
```

Breakdown dict changes from `dict[str, float | None]` to `dict[str, BreakdownEntry]`.

Serialization handled via `default=str` in `json.dumps` or a custom serializer.

### Step 1.5: Unify output wrapper

**Files:** `ceche/interfaces/cli/__init__.py:224-227`, `ceche/interfaces/cli/__init__.py:400-442`, `ceche/interfaces/cli/__init__.py:198-228`

Create a single `_output_result(result, format)` function. Both `appraise` and `bulk` produce the same outer schema:

```json
{
  "version": "2.2.0",
  "generated_at": "2026-07-16T13:45:22Z",
  "summary": { "total": 1, "succeeded": 1, "failed": 0, ... },
  "results": [ ... ],
  "failures": [ ... ]
}
```

`appraise` wraps single result into this schema. `bulk` already uses it. Both call the same `_output_result()`.

CSV and JSON Lines formatters go here in Phase 3.

### Phase 1 Tests

**File:** `tests/test_engine.py` — update assertions for new output schema
**File:** `tests/test_output_schema.py` — NEW: validate schema consistency across appraise/bulk

---

## Phase 2: Config System

**Goal:** File-based config with cascade, CLI `config` command group.

**Duration:** 2 sessions
**New files:** 3
**Modified files:** 2
**Net commands gained:** 7

### Step 2.1: Config loader

**New file:** `ceche/infrastructure/config/loader.py`

```python
class ConfigLoader:
    """Load config from cascade: env > project .ceche.toml > global config.toml > defaults"""

    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ceche" / "config.toml"
    PROJECT_CONFIG_NAME = ".ceche.toml"

    def load(self) -> Config:
        ...

    def resolve(self, key: str) -> str:
        """Resolve a key through the cascade chain."""
        ...
```

### Step 2.2: Config store

**New file:** `ceche/infrastructure/config/store.py`

```python
class ConfigStore:
    """Read/write TOML config files."""

    def read(self, path: Path) -> dict: ...
    def write(self, path: Path, data: dict) -> None: ...
    def set(self, key: str, value: str, global_: bool = False) -> None: ...
    def reset(self, global_: bool = False) -> None: ...
```

### Step 2.3: Config CLI commands

**New file:** `ceche/interfaces/cli/config_cmd.py`

```
ceche config show       → prints resolved config as table or JSON
ceche config path       → prints cascade paths in load order
ceche config set k v    → write key to project or global config
ceche config reset      → delete config file, restore defaults
ceche config import f   → import JSON/TOML
ceche config export f   → export current config
```

### Step 2.4: Profile support

```
ceche config profile list
ceche config profile create <name>
ceche config profile use <name>
ceche config profile delete <name>
```

Profiles stored in `~/.config/ceche/profiles/<name>.toml`.

### Step 2.5: Wire into existing code

**File:** `ceche/interfaces/cli/__init__.py` — replace `Config.load()` with `ConfigLoader().load()`
**File:** `ceche/config.py` — add new fields (concurrency, format defaults, etc.)

---

## Phase 3: Output Engine

**Goal:** CSV, JSON Lines, file output, filter/sort/module-select.

**Duration:** 2 sessions
**New files:** 4
**Modified files:** 1
**Net commands gained:** 0 (flags on existing commands)

### Step 3.1: Output Engine

**New file:** `ceche/interfaces/output/engine.py`

```python
class OutputEngine:
    def __init__(self, report: BulkReport, opts: OutputOptions): ...

    def apply_filters(self) -> OutputEngine: ...  # chainable
    def apply_sort(self) -> OutputEngine: ...
    def apply_pagination(self) -> OutputEngine: ...

    def to_json(self) -> str: ...
    def to_jsonl(self) -> Iterable[str]: ...
    def to_csv(self) -> str: ...
    def to_table(self) -> Table: ...
    def to_pretty(self) -> str: ...

    def write(self, path: Path | None = None) -> None: ...
```

### Step 3.2: Filter chain

**New file:** `ceche/interfaces/output/filters.py`

```python
@dataclass
class FilterOptions:
    min_value: float | None = None
    max_value: float | None = None
    tld: str | None = None
    confidence: str | None = None
    registered: bool | None = None
    brandable: bool | None = None
    keyword: bool | None = None
    word_count: int | None = None
    min_age: float | None = None
    max_age: float | None = None

class DomainFilter:
    def apply(self, results: list[AppraisalResult], opts: FilterOptions) -> list[AppraisalResult]:
        ...
```

### Step 3.3: CSV formatter

**New file:** `ceche/interfaces/output/formatters/csv.py`

Columns: `domain, estimated_value, range_low, range_high, confidence, completeness_ratio, tld_score, weight_profile, registered, age_years, word_count, m6_status, ...`

### Step 3.4: JSON Lines formatter

**New file:** `ceche/interfaces/output/formatters/jsonl.py`

One JSON object per line. Streaming-friendly for piping into jq, databases.

### Step 3.5: Wire filter/sort flags into both commands

**File:** `ceche/interfaces/cli/__init__.py`

Add flag definitions to both `appraise_cmd` and `bulk_cmd`. Both call the shared `OutputEngine`.

---

## Phase 4: Persistence Layer

**Goal:** History, stats, cache management.

**Duration:** 3 sessions
**New files:** 4
**Modified files:** 2
**Net commands gained:** 8

### Step 4.1: SQLite store schema

**New file:** `ceche/infrastructure/persistence/models.py`

Tables:
- `runs` — batch metadata (id, started_at, duration_ms, total, succeeded, failed, version, fresh)
- `appraisals` — per-domain results (run_id, domain, estimated_value, confidence, modules_json, ...)
- `ai_usage` — token tracking (run_id, provider, model, tokens_in, tokens_out, cost_usd, latency_ms)

### Step 4.2: AppraisalStore

**New file:** `ceche/infrastructure/persistence/store.py`

```python
class AppraisalStore:
    def record_run(self, report: BulkReport, duration_ms: int) -> str: ...
    def get_run(self, run_id: str) -> RunRecord: ...
    def list_runs(self, days: int = 30) -> list[RunRecord]: ...
    def get_domain_history(self, domain: str, days: int = 90) -> list[AppraisalRecord]: ...
    def get_stats(self, days: int | None = None) -> Stats: ...
    def get_ai_usage(self, days: int, provider: str | None) -> list[AIUsageRecord]: ...
    def clear(self) -> None: ...
    def export(self, path: Path) -> None: ...
```

### Step 4.3: Wire auto-logging

**File:** `ceche/interfaces/cli/__init__.py` — after each `bulk` or `appraise` run, auto-record to store.

### Step 4.4: CLI commands

**New file:** `ceche/interfaces/cli/history_cmd.py` — `ceche history`
**New file:** `ceche/interfaces/cli/stats_cmd.py` — `ceche stats`

### Step 4.5: Cache management CLI

**New file:** `ceche/interfaces/cli/cache_cmd.py` — `ceche cache show/stats/clear/warm`

### Step 4.6: CacheStore upgrades

**File:** `ceche/infrastructure/cache/sqlite_adapter.py`

Add: cache stats (hit rate, entry count, size per adapter), TTL config per adapter.

---

## Phase 5: Portfolio System

**Goal:** Domain collection management.

**Duration:** 2 sessions
**New files:** 2
**New commands gained:** 13

### Step 5.1: PortfolioStore

**New file:** `ceche/infrastructure/portfolio/store.py`

Tables:
- `portfolios` (id, name, created_at)
- `portfolio_domains` (portfolio_id, domain, added_at, tags, notes)

### Step 5.2: CLI commands

**New file:** `ceche/interfaces/cli/portfolio_cmd.py`

```
ceche portfolio create <name>
ceche portfolio list
ceche portfolio show <name>
ceche portfolio delete <name>
ceche portfolio add <name> <domains...>
ceche portfolio remove <name> <domains...>
ceche portfolio appraise <name> [--fresh] [--concurrency N]
ceche portfolio value <name>
ceche portfolio import <name> <file>
ceche portfolio export <name> <file>
ceche portfolio tag <name> <domain> <tag>
ceche portfolio note <name> <domain> <note>
ceche portfolio search <query>
```

---

## Phase 6: Server + Web + TUI

**Goal:** Multi-mode interface (HTTP API, Web dashboard, Terminal UI).

**Duration:** 3 sessions
**New files:** 8
**New commands gained:** 3

### Step 6.1: FastAPI server

**New file:** `ceche/interfaces/api/app.py`

Endpoints:
- `POST /appraise` — single domain
- `POST /bulk` — batch appraisal
- `GET /health` — adapter health check
- `GET /stats` — usage statistics
- `GET /history` — appraisal history
- `GET /portfolios` — portfolio list
- `POST /portfolios/{id}/appraise` — appraise portfolio

### Step 6.2: `ceche serve`

**New file:** `ceche/interfaces/cli/serve_cmd.py`

Start FastAPI via uvicorn. Port/host/workers configurable.

### Step 6.3: Web dashboard

**New file:** `ceche/interfaces/web/index.html` + static assets

Simple HTML/JS dashboard served by FastAPI. Shows recent appraisals, portfolio values, health status.

### Step 6.4: `ceche web`

Same as serve but opens browser to dashboard on start.

### Step 6.5: Terminal UI

**New file:** `ceche/interfaces/tui/app.py`

Rich-based TUI:
- Domain search bar
- Portfolio browser
- Live appraisal viewer
- Settings panel

### Step 6.6: `ceche tui`

Launch the TUI.

---

## Phase 7: Advanced Features

**Goal:** Watch, schedule, compare, diff, similar, plugins, deploy.

**Duration:** 5 sessions
**New files:** 12
**New commands gained:** 30

### Step 7.1: Watch mode

**New file:** `ceche/interfaces/cli/watch_cmd.py`

```
ceche watch <file> [--interval N] [--webhook URL] [--notify slack|discord]
```

Uses `watchfiles` for inotify. When file changes, runs bulk appraisal. Optional webhook/notification on completion.

### Step 7.2: Schedule

**New file:** `ceche/interfaces/cli/schedule_cmd.py`

```
ceche schedule <file> [--cron expr] [--list] [--remove ID]
```

Persists schedule config. Background process or relies on external cron.

### Step 7.3: Compare

**New file:** `ceche/interfaces/cli/compare_cmd.py`

```
ceche compare <d1> <d2> [--format json|table]
```

Runs appraisal on both domains, produces side-by-side module diff.

### Step 7.4: Diff

**New file:** `ceche/interfaces/cli/diff_cmd.py`

```
ceche diff <domain> [--since DATE]
```

Queries history store for previous appraisals, compares module-by-module.

### Step 7.5: Similar

**New file:** `ceche/interfaces/cli/similar_cmd.py`

```
ceche similar <domain> [--limit N] [--tld ext]
```

Word manipulation: add/remove characters, swap TLDs, synonym substitution. Appraises each candidate, sorts by value.

### Step 7.6: Retry

**New file:** `ceche/interfaces/cli/retry_cmd.py`

```
ceche retry <run-id> [--failed-only]
```

Replays domains from a previous run, using same engine config.

### Step 7.7: Plugin system

**New file:** `ceche/infrastructure/plugins/loader.py`
**New file:** `ceche/interfaces/cli/plugin_cmd.py`

```
ceche plugin list
ceche plugin install <name>
ceche plugin remove <name>
ceche plugin enable|disable <name>
```

Plugins are Python packages that register custom modules, adapters, or formatters. Discovery via entry points: `ceche.plugins`.

### Step 7.8: Benchmark

**New file:** `ceche/interfaces/cli/benchmark_cmd.py`

```
ceche benchmark <file> [--concurrency 1,5,10] [--runs 3]
```

Runs bulk appraisal at multiple concurrency levels. Reports P50/P95/P99 latency, throughput, token cost.

### Step 7.9: Debug

**New file:** `ceche/interfaces/cli/debug_cmd.py`

```
ceche debug <domain> [--dry-run] [--trace] [--verbose]
```

Dry-run mode uses mock adapters. Trace mode prints per-module timing and raw data. Verbose shows full log output.

### Step 7.10: Upgrade

**New file:** `ceche/interfaces/cli/upgrade_cmd.py`

```
ceche upgrade [--check] [--method pip|pipx]
```

Calls PyPI JSON API for latest version, runs `pip install --upgrade ceche[cli]`.

### Step 7.11: Uninstall

**File:** `ceche/interfaces/cli/__init__.py`

```
ceche uninstall [--keep-config] [--keep-data] [--dry-run]
```

### Step 7.12: Completions

**File:** `ceche/interfaces/cli/__init__.py`

```
ceche completion bash|zsh|fish
```

Generates shell completion script via Typer's built-in support.

### Step 7.13: Deploy artifacts

**New files:**
- `Dockerfile` — multi-stage Python build
- `docker-compose.yml` — ceche + optional Redis for caching
- `charts/ceche/` — Helm chart for Kubernetes

### Step 7.14: Demo

**New file:** `ceche/interfaces/cli/demo_cmd.py`

```
ceche demo [--domains N] [--format pretty]
```

Generates N fake domains with mock data. Useful for screenshots, walkthroughs.

### Step 7.15: Validate

**New file:** `ceche/interfaces/cli/validate_cmd.py`

```
ceche validate <config-file>
```

Validates config against schema. Returns errors with line numbers.

### Step 7.16: License

**New file:** `ceche/interfaces/cli/license_cmd.py`

```
ceche license [--activate KEY] [--status]
```

Enterprise license validation.

---

## Summary

| Phase | Commands Gained | New Files | Modified Files | Sessions |
|---|---|---|---|---|
| 1: Output Cleanup | 0 | 0 | 5 | 1 |
| 2: Config System | 7 | 3 | 2 | 2 |
| 3: Output Engine | 0 (flags) | 4 | 1 | 2 |
| 4: Persistence | 8 | 4 | 2 | 3 |
| 5: Portfolios | 13 | 2 | 1 | 2 |
| 6: Server/Web/TUI | 3 | 8 | 1 | 3 |
| 7: Advanced | 30 | 12 | 1 | 5 |
| **Total** | **61 new** | **33** | **13** | **18** |

---

## Phase 1 Immediate Plan (Ready to Start)

### Files to create

| # | File | Purpose |
|---|---|---|
| 1 | `tests/test_output_schema.py` | Schema validation tests |

### Files to modify

| # | File | Changes |
|---|---|---|
| 1 | `ceche/engine.py` | Fix `_module_breakdown` status, add 14-slot guarantee, add version/generated_at |
| 2 | `ceche/domain/result.py` | Add `version`, `generated_at` fields |
| 3 | `ceche/domain/modules/m15_pricing.py` | New `BreakdownEntry` dataclass, restructure breakdown |
| 4 | `ceche/interfaces/cli/__init__.py` | Unify output wrapper, refactor appraise_cmd |
| 5 | `tests/test_engine.py` | Update assertions |

### Key decisions

- **BreakdownEntry serialization:** use a custom `to_dict()` method on `BreakdownEntry` or convert to plain dict in `_module_breakdown`
- **M6 `result` field:** rename `status` → `result` only in output, keep `context["m6_status"]` unchanged internally
- **14-slot guarantee:** `_MODULE_NAMES` constant in engine ensures deterministic order and presence
- **Old `_module_status` key:** removed from output, never visible to user again
