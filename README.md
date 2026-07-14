# Ceche — Domain Appraisal Engine

A modular, free-tier domain appraisal tool that evaluates any domain string — registered or unregistered — across 16 dimensions and produces a dollar value estimate.

## Overview

```
ceche appraise example.com
```

Ceche scores a domain on length, word count, pronounceability, keyword popularity, commercial intent, search presence, trademark risk, history, authority, and brandability. The outputs compound through a multiplier-based valuation model to produce realistic price ranges.

## Quick Start

```bash
# Install
pip install ceche

# Appraise a domain
ceche appraise example.com

# Batch appraisal from file
ceche appraise domains.txt

# Output as JSON
ceche appraise example.com --format json

# Fresh lookups (bypass cache)
ceche appraise example.com --fresh
```

## Architecture

16 independent modules, each scoring one dimension:

| # | Module | Source | Cost |
|---|---|---|---|
| M1 | RDAP / WHOIS | rdap.org | Free |
| M2 | TLD Score Table | Static JSON (54 TLDs) | Free |
| M3 | Character Length | Local code | Free |
| M4 | Word-Count | Reads from M6 | Free |
| M5 | Pronounceability | Local logic | Free |
| M6 | Segmenter | wordfreq + DP | Free |
| M7 | Keyword Popularity | pytrends + static | Free |
| M8 | CPC / Commercial Intent | Static 5K keyword map | Free |
| M9 | Search Results | Google CSE + Brave | Free tier |
| M10 | Cross-TLD Check | RDAP (reuses M1) | Free |
| M11 | Trademark Check | USPTO + EUIPO | Free |
| M12 | Backlink/History/Age | Wayback + Ahrefs + OPR | Free tier |
| M13 | Confidence Flag | Local logic | Free |
| M14 | Caching Layer | SQLite | Free |
| M15 | Pricing / Valuation | Multiplier math | Free |
| M16 | Brandability | Local logic | Free |

## Valuation Model

Ceche uses a **multiplier-based** system:

```
value = tld_base × multiplier_m4 × multiplier_m3 × multiplier_m7 × ...
```

Each module returns a multiplier (e.g., single word = ×20, 3 chars = ×15, high CPC = ×5). Multipliers compound naturally — a 3-letter single-word .com with high commercial intent values vastly more than a 12-character 3-word .icu, without artificial caps or linear percentages.

## Documentation

See the `docs/` directory for full documentation:

| File | Contents |
|---|---|
| `01-architecture-overview.md` | System architecture, pipeline flow, multiplier model |
| `02-module-specifications.md` | All 16 modules — detailed specs for each |
| `03-tld-score-table.md` | TLD rankings (1–10), weight profiles per tier |
| `04-scoring-and-valuation.md` | Multiplier math, worked examples |
| `05-caching-layer.md` | SQLite schema, key format, TTLs |
| `06-configuration.md` | Config file, environment variables, CLI flags |
| `07-ai-enhancements.md` | AI-powered refinement for M6, M16, M15 |
| `08-cli-usage.md` | Commands, flags, output formats |
| `09-build-order.md` | Phase-by-phase implementation sequence |
| `10-data-sources.md` | All external APIs, rate limits, attribution |

## Requirements

- Python 3.10+
- API keys (optional — modules degrade gracefully):
  - Google CSE API key (M9 — search results)
  - Brave Search API key (M9 — search results backup)
  - Keywords Everywhere account (M12 — OpenPageRank)

## License

MIT
