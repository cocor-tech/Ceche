# Ceche — Domain Appraisal Engine

A modular domain appraisal tool that evaluates any domain across 16 dimensions and produces a dollar value estimate.

## Quick Start

```bash
pip install ceche

# Single domain
ceche check example.com

# Bulk from file
ceche bulk domains.txt -c 10

# Terminal UI
ceche start

# HTTP API server
ceche server serve --port 8080
```

## All Commands

```
check <domain...>       Appraise 1-N domains
bulk <domains...>       Concurrent bulk appraisal
start                   Launch terminal UI
keys                    List stored API keys
key-add                 Add an API key
key-remove <id>         Remove an API key
profiles                List config profiles
profile-create <name>   Create a profile
profile-use <name>      Activate a profile
profile-delete <name>   Delete a profile
history                 View appraisal history
history export <file>   Export history
history clear           Clear history
stats                   Usage statistics
cache                   Cache info
cache clear             Clear cache
cache stats             Cache statistics
cache ttl <sec>         Set cache TTL
config                  Show configuration
config set <k> <v>      Set config value
config path             Show config file paths
config reset            Reset to defaults
config import <file>    Import config
config export <file>    Export config
compare <d1> <d2>       Side-by-side comparison
diff <domain>           Value history
similar <domain>        Find similar domains
retry <run-id>          Re-appraise past run
debug <domain>          Debug appraisal
demo                    Demo with mock data
version                 Show version
version check           Check for updates
version upgrade         Install update
serve                   Start HTTP API
web                     Start + open dashboard
shell <shell>           Generate completions
portfolio                Portfolio management (13 subcommands)
watch <file>            Watch file for new domains
```

## Output Formats

```
ceche check example.com --format json       # JSON (default)
ceche check example.com --format csv        # CSV
ceche check example.com --format jsonl      # JSON Lines
ceche check example.com --format table      # Rich table
ceche check example.com --format pretty     # Human-readable
```

## Filter & Sort

```
ceche check domains.txt --min-value 10000 --tld com --sort value --limit 10
ceche bulk domains.txt --registered --confidence high --sort name --sort-order desc
```

## Configuration

Config cascade: env vars > `.ceche.toml` > `~/.config/ceche/config.toml` > defaults

```
ceche config set concurrency 20
ceche config set format json
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CECHE_AI_ENABLED` | false | Enable AI features |
| `CECHE_GOOGLE_CSE_KEY` | — | Google Custom Search key |
| `CECHE_GOOGLE_CSE_CX` | — | Google CSE context |
| `CECHE_BRAVE_KEY` | — | Brave Search key |
| `CECHE_OPR_KEY` | — | Open PageRank key |
| `CECHE_CONCURRENCY` | 10 | Default concurrency |
| `CECHE_FORMAT` | pretty | Default output format |
| `CECHE_CACHE_PATH` | cache.db | Cache file location |
| `CECHE_AI_TEMPERATURE` | 0.1 | AI model temperature |
| `CECHE_AI_MAX_TOKENS` | 150 | AI max tokens |

## Installation

```bash
pip install ceche                    # CLI only
pip install ceche[web]               # + HTTP server
pip install ceche[tui]               # + Terminal UI
pip install ceche[all]               # everything
```

## Development

```bash
pip install -e ".[dev]"
ruff check .
mypy ceche/ --ignore-missing-imports
pytest tests/
```

## Architecture

16 modules evaluate a domain across:
- M1: RDAP registration data
- M2: TLD tier scoring
- M3: SLD length analysis
- M4: Word count multiplier
- M5: Pronounceability scoring
- M6: Word segmentation
- M7: Keyword popularity
- M8: CPC/commercial intent
- M9: Search result counts
- M10: Cross-TLD registration check
- M11: Trademark conflicts
- M12: Domain authority signals
- M13: Confidence scoring
- M15: Multiplier-based pricing
- M16: Brand name quality

## License

MIT
