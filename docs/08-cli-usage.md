# CLI Usage

## Basic Usage

```
ceche appraise <domain> [<domain> ...]
ceche appraise <filename>
```

### Single Domain

```bash
ceche appraise example.com
```

### Multiple Domains

```bash
ceche appraise example.com car.com nekwasa.com
```

### Batch from File

```bash
ceche appraise domains.txt
```

One domain per line. Blank lines and comments (#) are ignored.

---

## Options

| Flag | Description |
|---|---|
| `--fresh`, `-f` | Bypass cache for all lookups |
| `--format <type>` | Output format: `json` (default), `table`, `pretty` |
| `--include-raw`, `-r` | Include per-module raw data in output |
| `--skip <modules>` | Comma-separated module names to skip (e.g., `m8,m12`) |
| `--only <modules>` | Comma-separated module names to run exclusively |
| `--config <path>` | Path to custom config file |
| `--quiet`, `-q` | Suppress progress output, only print results |
| `--no-color` | Disable colored output |
| `--version` | Print version and exit |
| `--help`, `-h` | Show help message |

---

## Output Formats

### JSON (default)

```json
{
  "domain": "example.com",
  "tld": "com",
  "tld_score": 10,
  "tld_base": 100,
  "estimated_value": 4320000,
  "range": {
    "low": 4320000,
    "high": 4320000
  },
  "confidence": "high",
  "completeness_ratio": 1.0,
  "missing_signals": [],
  "cache": {
    "hits": 4,
    "misses": 2,
    "rate": 0.67
  },
  "modules": {
    "m1_rdap": {
      "age_years": 27,
      "registered": true,
      "multiplier": 3
    },
    "m3_length": {
      "score": 98,
      "multiplier": 15
    },
    "m4_word_count": {
      "words": 1,
      "multiplier": 20
    },
    "m5_pronounceability": {
      "score": 98,
      "multiplier": 2
    },
    "m7_keyword_popularity": {
      "score": 95,
      "multiplier": 8
    },
    "m8_cpc": {
      "tier": "informational",
      "multiplier": 1
    },
    "m11_trademark": {
      "conflict": false,
      "multiplier": 1
    },
    "m12_authority": {
      "authority_score": 100,
      "snapshots": 5000,
      "parked": false,
      "multiplier": 3
    }
  }
}
```

### Table

```
Domain         Estimate       Range                  Confidence  Missing     
─────────────────────────────────────────────────────────────────────────────
abc.com        $4,320,000     $4,320,000 - $4,320,000  high        None
car.com        $21,600,000    $21,600,000 - $21,600,000 high        None
nekwasa.com    $1,500         $1,219 - $1,781           medium      M1, M12
sadmecry.com   $810            $658 - $962               medium      M1, M12
```

### Pretty (human-readable)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Ceche — Domain Appraisal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Domain:          abc.com
  TLD:             .com (tier 10)
  Base:            $100

  Estimated Value: $4,320,000
  Range:           $4,320,000 – $4,320,000
  Confidence:      high

  Module Breakdown:
    M4  Word Count        1 word          ×20
    M3  Length            3 chars         ×15
    M7  Popularity        95/100          ×8
    M8  CPC               informational   ×1
    M11 Trademark         no conflict     ×1
    M5  Pronounceability  98/100          ×2
    M1  Age               27 years        ×3
    M12 History           5000 snapshots  ×3
    ─────────────────────────────────────────
    Product:   20 × 15 × 8 × 1 × 1 × 2 × 3 × 3 = 43,200
    Value:     $100 × 43,200 = $4,320,000

  Cache:  4 hits / 2 misses (67%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | All domains appraised successfully |
| 1 | Some domains failed (mixed results) |
| 2 | All domains failed (error in pipeline) |
| 3 | Configuration error (invalid config file) |
| 4 | Missing API key (when required) |

---

## Examples

```bash
# Simple appraisal
ceche appraise example.com

# Batch with custom config and fresh lookups
ceche appraise domains.txt --fresh --config ./production.toml

# Skip specific modules (when they're rate-limited)
ceche appraise example.com --skip m7,m9

# Only run specific modules (debugging)
ceche appraise example.com --only m1,m3,m4

# Quiet JSON output for piping to other tools
ceche appraise example.com --quiet --format json | jq '.estimated_value'

# Include raw data for analysis
ceche appraise example.com --include-raw > appraisal.json
```
