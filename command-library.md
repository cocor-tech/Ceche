# Ceche Command Library

Every command in the Ceche ecosystem. Existing commands marked `[EXISTS]`, all others planned.

---

## Legend

- `[EXISTS]` — Implemented and working
- `<required>` — Required argument
- `[optional]` — Optional argument
- `...` — Accepts multiple values

---

## Top-Level

| Command | Status | Description |
|---|---|---|
| `ceche --version` | PLANNED | Print version and exit |
| `ceche --help` | EXISTS | Show help |
| `ceche completion <shell>` | PLANNED | Generate shell completion for bash/zsh/fish |

---

## Core Appraisal

### `ceche appraise`

```
ceche appraise <domains...>

  --fresh, -f              Bypass cache
  --format, -F FORMAT      json | jsonl | csv | table | pretty
  --output, -o FILE        Write to file instead of stdout
  --quiet, -q              Suppress progress output
  --concurrency, -c N      Parallel domains (default 1)
  --modules M1,M3,M15      Only include specified modules
```

[EXISTS] Basic appraise works. PLANNED: unified schema, csv/jsonl, `-o`, `--modules`, `--concurrency`.

---

### `ceche bulk`

```
ceche bulk <domains...>
  ceche bulk domains.txt
  cat domains.txt | ceche bulk

  --concurrency, -c N      Max concurrent domains (default 10, range 1-100)
  --fresh, -f              Bypass all caches
  --format, -F FORMAT      json | jsonl | csv (default json)
  --output, -o FILE        Write to file instead of stdout
  --modules M1,M3,M15      Only include specified modules
```

[EXISTS] Core bulk works with json, concurrency, stdin pipe, file input, progress bar.

---

### Filtering & Sorting (applies to both `appraise` and `bulk`)

```
  --min-value N            Minimum estimated value
  --max-value N            Maximum estimated value
  --tld EXT                Filter by TLD (e.g., com, io, ai)
  --confidence LEVEL       Filter by confidence: high, medium, low, very_low
  --registered             Only registered domains
  --unregistered           Only unregistered domains
  --brandable              Only brandable (no_split) domains
  --keyword                Only keyword (split_found) domains
  --word-count N           Exact word count
  --min-age N              Minimum domain age in years
  --max-age N              Maximum domain age in years

  --sort FIELD             Sort by: value, name, tld, confidence, age, word_count
  --sort-order ORDER       asc (default) or desc

  --limit N                Show only first N results
  --skip N                 Skip first N results
  --sample N               Random sample of N results
```

PLANNED: All filter/sort/pagination flags.

---

## Comparison & Differencing

### `ceche compare`

```
ceche compare <domain1> <domain2>

  --format FORMAT          json | table (default table)
  --modules M1,M3,M15      Modules to include in comparison
```

PLANNED. Side-by-side module diff between two domains.

### `ceche diff`

```
ceche diff <domain>

  --since DATE             Compare appraisal from DATE to now
  --before ID1 --after ID2 Compare two specific appraisal runs
  --format FORMAT          json | table
```

PLANNED. Track value and module changes over time for a single domain.

### `ceche similar`

```
ceche similar <domain>

  --limit N                Max suggestions (default 10)
  --tld EXT                Restrict to TLD
```

PLANNED. Generate similar domain suggestions via word manipulation.

---

## Config System

### `ceche config show`

PLANNED. Pretty-print resolved configuration showing cascade.

### `ceche config path`

PLANNED. Print config file paths in load order.

### `ceche config set`

```
ceche config set <key> <value>

  --global                 Write to global config instead of project
```

PLANNED. Set configuration values.

### `ceche config reset`

PLANNED. Reset config to defaults.

### `ceche config import`

```
ceche config import <file>
```

PLANNED. Import config from JSON or TOML file.

### `ceche config export`

```
ceche config export <file>
```

PLANNED. Export current config to file.

### `ceche config profile`

```
ceche config profile list
ceche config profile create <name>
ceche config profile use <name>
ceche config profile delete <name>
```

PLANNED. Named configuration profiles.

---

## AI & Provider Management

### `ceche ai key-add`

```
ceche ai key-add

  --provider, -p PROVIDER  deepseek, openai, kimi, glm, minimax
  --key, -k KEY            API key string
  --label, -l LABEL        Optional label
  --expiry, -e EXPIRY      24h, 7d, 30d, 365d, forever
```

[EXISTS]

### `ceche ai key-list`

[EXISTS] List all stored keys with status.

### `ceche ai key-remove`

```
ceche ai key-remove <key-id>
```

[EXISTS] Revoke a key.

### `ceche ai key-rotate`

```
ceche ai key-rotate <key-id>

  --key, -k NEW-KEY        New API key
```

PLANNED. Rotate key without losing the key ID.

### `ceche providers`

```
ceche providers

  --refresh                Refresh model cache from provider APIs
  --format FORMAT          json | table
```

PLANNED. List configured AI providers and their models.

### `ceche providers test`

```
ceche providers test <provider>
```

PLANNED. Test connection to an AI provider.

### `ceche providers models`

```
ceche providers models <provider>
```

PLANNED. List available models for a provider.

---

## Health & Diagnostics

### `ceche health`

```
ceche health

  --rdap                   Only check RDAP connectivity
  --ai                     Only check AI providers
  --search                 Only check search APIs
  --authority              Only check authority (Wayback, Ahrefs, OPR)
  --all                    Check everything (default)
  --format FORMAT          json | table
```

PLANNED. Check all configured adapters are reachable and authenticated.

### `ceche debug`

```
ceche debug <domain>

  --dry-run                No network calls, use mock data
  --trace                  Per-module timing and raw data dump
  --verbose                Detailed logging
  --dump-config            Print resolved config
  --dump-modules           Print all module data before serialization
```

PLANNED. Debug a single domain appraisal step by step.

### `ceche validate`

```
ceche validate <config-file>
ceche validate --schema-only
```

PLANNED. Validate config file structure.

---

## History & Audit

### `ceche history`

```
ceche history

  --days N                 Show last N days (default 30)
  --domain DOMAIN          Filter by domain
  --format FORMAT          json | table
  --export FILE            Export history to file
  --clear                  Clear all history
```

PLANNED. View appraisal history.

### `ceche retry`

```
ceche retry <run-id>

  --failed-only            Only retry domains that failed
  --concurrency N          Concurrency for retry
```

PLANNED. Re-run domains from a previous appraisal run.

---

## Statistics & Analytics

### `ceche stats`

```
ceche stats

  --days N                 Show stats for last N days (default: all time)
  --format FORMAT          json | table
  --provider PROVIDER      Filter by AI provider
```

PLANNED. Token usage, cost, appraisal counts.

---

## Cache Management

### `ceche cache show`

PLANNED. Show current cache location and size.

### `ceche cache stats`

PLANNED. Cache hit/miss ratio, entry count, size per adapter.

### `ceche cache clear`

```
ceche cache clear
ceche cache clear --provider rdap
ceche cache clear --provider search
ceche cache clear --provider ai
ceche cache clear --provider authority
```

PLANNED. Clear cache entirely or by adapter.

### `ceche cache warm`

```
ceche cache warm <file>
```

PLANNED. Preload cache for domains in file.

### `ceche cache ttl`

```
ceche cache ttl <provider> <seconds>
```

PLANNED. Set per-adapter cache TTL.

---

## Portfolio Management

### `ceche portfolio create`

```
ceche portfolio create <name>
```

PLANNED.

### `ceche portfolio list`

PLANNED.

### `ceche portfolio show`

```
ceche portfolio show <name>
```

PLANNED.

### `ceche portfolio delete`

```
ceche portfolio delete <name>
```

PLANNED.

### `ceche portfolio add`

```
ceche portfolio add <name> <domains...>
ceche portfolio add <name> domains.txt
```

PLANNED.

### `ceche portfolio remove`

```
ceche portfolio remove <name> <domains...>
```

PLANNED.

### `ceche portfolio appraise`

```
ceche portfolio appraise <name>

  --fresh, -f
  --concurrency N
```

PLANNED. Appraise all domains in a portfolio.

### `ceche portfolio value`

```
ceche portfolio value <name>

  --format FORMAT
```

PLANNED. Aggregate valuation of all domains in portfolio.

### `ceche portfolio import`

```
ceche portfolio import <name> <file>
```

PLANNED. Import domains from CSV or JSON.

### `ceche portfolio export`

```
ceche portfolio export <name> <file>

  --format FORMAT          csv | json
```

PLANNED.

### `ceche portfolio tag`

```
ceche portfolio tag <name> <domain> <tag>
```

PLANNED. Tag a domain in a portfolio.

### `ceche portfolio note`

```
ceche portfolio note <name> <domain> <note>
```

PLANNED. Add a note to a domain.

### `ceche portfolio search`

```
ceche portfolio search <query>
```

PLANNED. Search across all portfolios.

---

## Automation

### `ceche watch`

```
ceche watch <file>

  --interval N             Re-check interval in seconds (default 300)
  --webhook URL            POST results to URL on change
  --notify slack|discord   Send notification on change
```

PLANNED. Watch a file for new domains and auto-appraise.

### `ceche schedule`

```
ceche schedule <file>

  --cron "0 */6 * * *"     Cron expression for recurrence
  --list                   List active schedules
  --remove ID              Remove a schedule
```

PLANNED. Schedule recurring appraisals.

---

## Server & API

### `ceche serve`

```
ceche serve

  --port N                 Port (default 8080)
  --host HOST              Host (default 127.0.0.1)
  --workers N              Worker count (default 1)
```

PLANNED. Start HTTP API server (FastAPI).

### `ceche web`

```
ceche web

  --port N
  --host HOST
```

PLANNED. Start server + open browser dashboard.

### `ceche tui`

```
ceche tui

  --portfolios             Open portfolio browser
  --domain DOMAIN          Quick-appraise a domain
```

PLANNED. Rich-based terminal UI.

---

## Plugins

### `ceche plugin list`

PLANNED.

### `ceche plugin install`

```
ceche plugin install <name>
```

PLANNED.

### `ceche plugin remove`

```
ceche plugin remove <name>
```

PLANNED.

### `ceche plugin enable`

```
ceche plugin enable <name>
```

PLANNED.

### `ceche plugin disable`

```
ceche plugin disable <name>
```

PLANNED.

---

## Deployment

### `ceche upgrade`

```
ceche upgrade

  --check                  Only check for updates, don't install
  --method pip|pipx        Installation method
```

PLANNED. Self-update from PyPI.

### `ceche uninstall`

```
ceche uninstall

  --keep-config            Keep configuration files
  --keep-data              Keep history and portfolios
  --dry-run                Show what would be removed
```

PLANNED.

### `ceche license`

```
ceche license

  --activate KEY           Activate enterprise license
  --status                 Show license status
```

PLANNED. Enterprise license management.

---

## Demo & Benchmark

### `ceche demo`

```
ceche demo

  --domains N              Generate N mock domains (default 5)
  --format FORMAT
```

PLANNED. Quick demo with mock data, no network.

### `ceche benchmark`

```
ceche benchmark <file>

  --concurrency N          Concurrency levels to test (default 1,5,10)
  --runs N                 Runs per level (default 3)
  --format FORMAT
```

PLANNED. Performance benchmarking.

---

## Total Commands

| Group | Count | Existing |
|---|---|---|
| Core Appraisal | 2 + 14 flags | 2 commands, 5 flags |
| Comparison | 3 | 0 |
| Config | 7 | 0 |
| AI & Providers | 7 | 3 |
| Health & Debug | 3 | 0 |
| History | 2 | 0 |
| Stats | 1 | 0 |
| Cache | 5 | 0 |
| Portfolio | 13 | 0 |
| Automation | 2 | 0 |
| Server & API | 3 | 0 |
| Plugins | 5 | 0 |
| Deployment | 3 | 0 |
| Demo & Benchmark | 2 | 0 |
| **Total** | **70** | **5** |
