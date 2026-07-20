# Ceche — Domain Appraisal Engine

## Product Specification v2.0

---

## 1. Product Overview

Ceche is a domain appraisal engine that evaluates any domain string — registered or unregistered — across 16 independent scoring dimensions and produces a dollar value estimate with confidence range.

Unlike existing appraisal tools that rely on comparable sales databases (NameBio, DNJournal) or third-party valuation APIs (GoDaddy, Estibot), Ceche generates valuations entirely from first principles: it scores the domain's inherent characteristics (length, pronounceability, word composition), market signals (keyword popularity, commercial intent, search presence), and risk factors (trademark conflicts, cross-TLD competition), and compounds them through a multiplier-based model into a dollar figure.

The system is designed to operate on a $0–$2/month budget using exclusively free-tier and self-hosted tooling, with no paid API dependencies.

---

## 2. Architecture

### 2.1 Hexagonal (Ports & Adapters) Pattern

The codebase is structured into three fully separated layers with strict dependency rules. Domain code may never import infrastructure or interface code. Infrastructure implements domain-defined interfaces. Interfaces wire everything together.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          ceche (monorepo)                           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                     ceche/domain                             │    │
│  │  DEPENDENCIES: Python stdlib ONLY. No httpx, no FastAPI.    │    │
│  │                                                              │    │
│  │  ┌──────────────────────────────────────────────────────┐   │    │
│  │  │  Engine                                              │   │    │
│  │  │  - Orchestrates the appraisal pipeline               │   │    │
│  │  │  - Manages module execution order and concurrency    │   │    │
│  │  │  - Pure logic: no I/O, no network, no filesystem     │   │    │
│  │  └──────────────────────────────────────────────────────┘   │    │
│  │                                                              │    │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │    │
│  │  │ M1   │ │ M2   │ │ M3   │ │ M4   │ │ M5   │ │ M6   │   │    │
│  │  │EPort │ │Port  │ │      │ │      │ │      │ │      │   │    │
│  │  └──┬───┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘   │    │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │    │
│  │  │ M7   │ │ M8   │ │ M9   │ │ M10  │ │ M11  │ │ M12  │   │    │
│  │  │Port  │ │      │ │Port  │ │      │ │Port  │ │Port  │   │    │
│  │  └──┬───┘ └──────┘ └──┬───┘ └──────┘ └──┬───┘ └──┬───┘   │    │
│  │  ┌──────┐ ┌──────┐ ┌─┴────┐ ┌──────┐   │    ┌───┴───┐   │    │
│  │  │ M13  │ │ M14  │ │ M15  │ │ M16  │   │    │       │   │    │
│  │  │      │ │Port  │ │      │ │      │   │    │       │   │    │
│  │  └──────┘ └──┬───┘ └──────┘ └──────┘   │    │       │   │    │
│  │              │                           │    │       │   │    │
│  │  ┌───────────┴───────────────────────────┴────┴───────┘   │    │
│  │  │  Ports (Abstract Interfaces)                            │    │
│  │  │  - RDAPPort              (M1)                           │    │
│  │  │  - CachePort             (M14)                          │    │
│  │  │  - TrademarkPort         (M11)                          │    │
│  │  │  - SearchPort            (M9)                           │    │
│  │  │  - AuthorityPort         (M12)                          │    │
│  │  │  - KeywordPopularityPort (M7)                           │    │
│  │  │  - ConfigPort            (all)                          │    │
│  │  └─────────────────────────────────────────────────────────┘    │
│  └─────────────────────────────────────────────────────────────────┘
│                              │
│  ┌─────────────────────────────────────────────────────────────────┐
│  │                    ceche/infrastructure                         │
│  │  DEPENDENCIES: Everything. Implements domain ports.            │
│  │                                                               │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐  │
│  │  │ RDAPAdapter  │ │ SQLiteCache  │ │ USPTOAdapter         │  │
│  │  │ (httpx)      │ │ (sqlite3)    │ │ (httpx + HTML parse) │  │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐  │
│  │  │ GoogleCSEAdapter          │ │ AhrefsDRAdapter │ │ OPRAdapter    │  │
│  │  │ (httpx)                    │ │ (httpx)         │ │ (httpx)       │  │
│  │  └────────────────────────────┘ └─────────────────┘ └──────────────┘  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐  │
│  │  │ pytrendsAdapter           │ │ WaybackAdapter │ │ BraveAdapter   │  │
│  │  │ (pytrends)    │ │ (httpx)         │ │ (httpx)          │  │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘  │
│  └─────────────────────────────────────────────────────────────────┘
│                              │
│  ┌─────────────────────────────────────────────────────────────────┐
│  │                   ceche/interfaces                              │
│  │  DEPENDENCIES: ceche/domain + ceche/infrastructure + framework │
│  │                                                               │
│  │  ┌────────────────────────┐  ┌─────────────────────────────┐  │
│  │  │  CLI (Typer)           │  │  Web API (FastAPI)          │  │
│  │  │                        │  │                             │  │
│  │  │  $ ceche appraise      │  │  POST /v1/appraise          │  │
│  │  │  $ ceche cache clear   │  │  GET  /v1/appraise/{id}     │  │
│  │  │  $ ceche config show   │  │  GET  /v1/health            │  │
│  │  │  $ ceche --version     │  │  GET  /v1/docs (Swagger)    │  │
│  │  └────────────────────────┘  └─────────────────────────────┘  │
│  └─────────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Dependency Rules

```
ceche/interfaces  ──imports──▶  ceche/domain  ◀──imports──  ceche/infrastructure
       │                                │
       └─────────── imports ────────────┘
```

- **domain/** imports NOTHING outside Python stdlib
- **infrastructure/** implements domain interfaces, imports third-party libs
- **interfaces/** wires domain + infrastructure together, adds framework (Typer, FastAPI)

### 2.3 Data Flow

```
Request (domain string)
    │
    ▼
[Interface Layer]
    │ Parses input, validates, loads config
    ▼
[Engine — Domain Layer]
    │ 1. Parse domain → SLD + TLD
    │ 2. Run M14 cache check (via CachePort)
    │ 3. Run M1 (RDAPPort), M6 (pure) in parallel
    │ 4. Run M2 (pure), M3 (pure), M4 (reads M6), M5 (pure)
    │ 5. Run M7 (KeywordPopularityPort), M8 (pure), M9 (SearchPort)
    │ 6. Run M10 (RDAPPort), M11 (TrademarkPort), M12 (AuthorityPort)
    │ 7. Run M16 (pure, if M6 = no_split)
    │ 8. Run M13 (pure), M15 (pure)
    │
    ▼
Result object (typed dataclass)
    │
    ▼
[Interface Layer]
    │ Formats to JSON / Console table / Pretty print
    ▼
Response
```

---

## 3. The 16 Modules

### 3.1 M1 — RDAP / WHOIS Lookup

**Purpose:** Registration status, domain age, registrar, expiry.

**Domain port:** `RDAPPort` — abstract interface for registration lookup.

**Infrastructure adapter:** `RDAPAdapter` — queries `rdap.org` via httpx.

**Output:**
- `registered: bool`
- `creation_date: date | None`
- `expiry_date: date | None`
- `registrar: str | None`
- `age_years: float | None`

### 3.2 M2 — TLD Score Table

**Purpose:** Assigns a 1–10 score to the TLD, selects the weight profile.

**Domain:** Pure lookup against embedded JSON data.

**Data file:** `ceche/domain/data/tld_scores.json` — 54 TLDs with custom scores, all others default to 0.2.

**Output:**
- `tld_score: float`
- `weight_profile: str` — identifier for M15 to select multiplier tables

### 3.3 M3 — Character Length Scorer

**Purpose:** Scores SLD length on an inverted sigmoid curve centered at 5.

**Domain:** Pure Python computation.

**Formula:** `score = 100 × (1 - 1 / (1 + e^(-0.8 × (len - 5))))`

**Output:** `internal_score: float` (0–100)

### 3.4 M4 — Word-Count Scorer

**Purpose:** Penalizes domains with multiple words.

**Domain:** Pure computation, reads M6's word count.

**Formula:** `score = 100 × e^(-0.5 × (words - 1))`

**Output:** `internal_score: float | None` (null if M6 returned no_split)

### 3.5 M5 — Pronounceability Scorer

**Purpose:** Rates how easily a string can be spoken.

**Domain:** Pure computation using vowel density + consonant cluster analysis + bigram frequency table.

**Output:** `internal_score: float` (0–100)

### 3.6 M6 — Segmenter

**Purpose:** Breaks domain into valid English word segmentations.

**Domain:** Dynamic programming word-break algorithm.

**Word list:** Embedded in domain layer (google-10000-english + wordfreq data bundled as module data).

**Output:**
- `winner: list[str] | None` (best segmentation or None if no split)
- `word_count: int | None`
- `confidence: float`

### 3.7 M7 — Keyword Popularity

**Purpose:** Search interest score for each segmented word.

**Domain port:** `KeywordPopularityPort` — abstract interface.

**Infrastructure adapters (tiered fallback):**
- **Primary:** `pytrendsAdapter` — wraps the pytrends library
- **Fallback:** `StaticKeywordAdapter` — embedded frequency map of ~10,000 English words

**Output:**
- `word_scores: dict[str, float]`
- `domain_score: float` — max of word scores
- `source: str` — which adapter served the result

### 3.8 M8 — CPC / Commercial Intent

**Purpose:** Commercial-intent tier based on known CPC values.

**Domain:** Pure lookup against embedded JSON map of ~5,000 high-CPC keywords.

**Data file:** `ceche/domain/data/cpc_keywords.json`

**Output:**
- `tier: str` — Elite | High | Medium-High | Medium | Low | Informational | None
- `match_word: str | None`

### 3.9 M9 — Search Results

**Purpose:** Search result presence and competing TLD detection.

**Domain port:** `SearchPort` — abstract interface.

**Infrastructure adapters (tiered fallback):**
- **Primary:** `GoogleCSEAdapter` — Google Programmable Search Engine API
- **Backup:** `BraveAdapter` — Brave Search API

**Output:**
- `result_count: int | None`
- `snippets: list[str]`
- `competing_tld: bool`

### 3.10 M10 — Cross-TLD Check

**Purpose:** Checks if the same SLD exists on other TLDs.

**Domain port:** Reuses `RDAPPort`.

**Infrastructure adapter:** Reuses `RDAPAdapter` against candidate TLDs (.com, .net, .org, .co, .io, .app, .dev, .xyz) + HTTP HEAD for content detection.

**Output:**
- `variants: dict[str, RegistrationStatus]`
- `strongest_active: str | None`

### 3.11 M11 — Trademark Check

**Purpose:** Flags trademark conflicts on segmented words.

**Domain port:** `TrademarkPort` — abstract interface.

**Infrastructure adapters:**
- `USPTOAdapter` — scrapes USPTO TSDR (free, no key)
- `EUIPOAdapter` — scrapes EUIPO eSearch (free, no key)

**Output:**
- `conflicts: list[TrademarkConflict]`
- `severity: str` — none | partial | exact

### 3.12 M12 — Backlink / History / Age

**Purpose:** Authority and history signals for registered domains.

**Domain port:** `AuthorityPort` — abstract interface.

**Infrastructure adapters:**
- `WaybackAdapter` — Wayback Machine CDX API (free, no key)
- `AhrefsDRAdapter` — Ahrefs free public DR endpoint (free, no key)
- `OPRAdapter` — OpenPageRank API (free tier, requires key)

**Signals:**
- Snapshot count + earliest date (Wayback)
- Domain Rating 0–100 (Ahrefs)
- OpenPageRank 0–10 + referring domains (OPR)
- Parked detection via snapshot analysis

### 3.13 M13 — Confidence Flag

**Purpose:** Aggregates module statuses into a completeness score.

**Domain:** Pure logic — reads statuses from all modules.

**Output:**
- `completeness_ratio: float`
- `confidence_label: str`
- `missing_signals: list[str]`

### 3.14 M14 — Caching Layer

**Purpose:** Cache external lookups by term/segment, keyed by `source:term`.

**Domain port:** `CachePort` — abstract interface.

**Infrastructure adapter:** `SQLiteCacheAdapter` — SQLite via Python's built-in `sqlite3`.

**Schema:**
```sql
CREATE TABLE cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    ttl INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);
```

**TTL table:** Module-dependent (24h for RDAP, 7d for search, 30d for CPC, 90d for TLD table).

### 3.15 M15 — Pricing / Valuation

**Purpose:** Converts all module outputs into a dollar estimate.

**Domain:** Pure computation — multiplier multiplication + confidence range.

**Formula:**
```
final_value = tld_base × m4_mult × m3_mult × m7_mult × m8_mult × m5_mult × m1_mult × m12_mult × m11_mult × m16_mult
```

**TLD base values:**
| Score | TLDs | Base |
|---|---|---|
| 10 | .com | $100 |
| 8–9 | .net, .io, .ai, .co, .de, .org | $50 |
| 7–7.5 | .app, .xyz, .us, .tv, .me, .tech | $30 |
| 6–6.5 | .world, .eu, .sh, .ca, .inc | $20 |
| 4–5 | .cloud, .blog, .news, .site | $10 |
| 1–3 | .icu, .biz, .one, .network | $5 |
| 0.2 | all others | $2 |

**Confidence range:**
```
range_low  = final_value × (1 - (1 - completeness_ratio) × 0.5)
range_high = final_value × (1 + (1 - completeness_ratio) × 0.5)
```

### 3.16 M16 — Brandability Scorer

**Purpose:** Assesses domains that have no dictionary words (M6 = no_split) as potential brand names.

**Domain:** Pure computation using letter-pattern analysis, syllable flow, bigram frequency, and cross-TLD availability data.

**Activation condition:** M6 returns `status: "no_split"` — this module replaces M4, M7, M8 for this domain.

**Output:**
- `brandability_score: float`
- `class: str` — high | medium | low

---

## 4. Valuation Model

### 4.1 Multiplier Tables

Each module's internal score (0–100 or classification) maps to a multiplier:

**M1 — Age:**
| Years | Multiplier |
|---|---|
| 20+ | ×3.0 |
| 10–20 | ×2.0 |
| 5–10 | ×1.5 |
| 1–5 | ×1.2 |
| <1 | ×1.0 |
| null (unregistered) | omitted |

**M3 — Length:**
| Chars | Multiplier |
|---|---|
| 1–3 | ×15 |
| 4–5 | ×8 |
| 6–7 | ×2 |
| 8–10 | ×1.2 |
| 11+ | ×1.0 |

**M4 — Word Count:**
| Words | Multiplier |
|---|---|
| 1 | ×20 |
| 2 | ×3 |
| 3 | ×1.5 |
| 4+ | ×1.0 |
| null | omitted |

**M5 — Pronounceability:**
| Score | Multiplier |
|---|---|
| >= 90 | ×2.0 |
| >= 70 | ×1.5 |
| >= 40 | ×1.2 |
| < 40 | ×1.0 |

**M7 — Keyword Popularity:**
| Score | Multiplier |
|---|---|
| >= 90 | ×8 |
| >= 70 | ×5 |
| >= 50 | ×3 |
| >= 30 | ×2 |
| >= 10 | ×1.5 |
| < 10 or null | ×1.0 |

**M8 — CPC Tier:**
| Tier | Multiplier |
|---|---|
| Elite | ×5 |
| High | ×3 |
| Medium-High | ×2.5 |
| Medium | ×2 |
| Low | ×1.5 |
| Informational / None | ×1.0 |

**M9 — Search Results:**
| Result count | Multiplier |
|---|---|
| 10,000+ | ×5 |
| 1,000+ | ×3 |
| 100+ | ×2 |
| 10+ | ×1.3 |
| <10 / null | ×1.0 |

**M10 — Cross-TLD:**
| Situation | Multiplier |
|---|---|
| .com being appraised | ×1.0 (always) |
| Non-.com, no active .com variant | ×1.0 |
| Non-.com, active .com variant | ×0.5 |

**M11 — Trademark:**
| Situation | Multiplier |
|---|---|
| No conflict | ×1.0 |
| Partial match | ×0.5 |
| Exact match, not the owner | ×0.1 |
| Exact match, IS the owner | ×1.0 |

**M12 — Authority:**
| Blended score | Multiplier |
|---|---|
| >= 90 | ×3 |
| >= 50 | ×2 |
| >= 20 | ×1.2 |
| < 20 or null | ×1.0 |

**M16 — Brandability:**
| Score | Multiplier |
|---|---|
| >= 80 | ×8 |
| >= 60 | ×5 |
| >= 40 | ×3 |
| >= 20 | ×2 |
| < 20 | ×1 |
| null | omitted |

### 4.2 Worked Examples

**abc.com** — 3-letter .com, registered, single dictionary word, elite scarcity:

```
TLD: .com (score 10), base = $100

M4: 1 word           → ×20
M3: 3 chars          → ×15
M7: "abc" very high  → ×8
M8: informational     → ×1
M11: no conflict      → ×1
M5: pronounceable     → ×2
M1: 27 years          → ×3
M12: extensive hist.  → ×3

Product: 20 × 15 × 8 × 1 × 1 × 2 × 3 × 3 = 43,200
Value:   $100 × 43,200 = $4,320,000
```

**car.com** — 3-letter dictionary word .com, high commercial intent:

```
TLD: .com, base = $100

M4: 1 word           → ×20
M3: 3 chars          → ×15
M7: "car" very high  → ×8
M8: auto CPC Elite   → ×5
M11: no conflict      → ×1
M5: pronounceable     → ×2
M1: 30+ years         → ×3
M12: extensive        → ×3

Product: 20 × 15 × 8 × 5 × 1 × 2 × 3 × 3 = 216,000
Value:   $100 × 216,000 = $21,600,000
```

**nekwasa.com** — brandable .com, unregistered, no dictionary words:

```
TLD: .com, base = $100

M6: no_split → brandable profile activates

M3: 7 chars          → ×2
M5: pronounceable     → ×1.5
M16: brandable        → ×5
M11: no conflict      → ×1
M1: (omitted)         → —
M12: (omitted)        → —

Product: 2 × 1.5 × 5 × 1 = 15
Value:   $100 × 15 = $1,500
```

**sadmecry.com** — 3-word .com, unregistered, low commercial intent:

```
TLD: .com, base = $100

M4: 3 words          → ×1.5
M3: 8 chars          → ×1.2
M7: "me" popular     → ×3
M8: informational     → ×1
M11: no conflict      → ×1
M5: pronounceable     → ×1.5
M1: (omitted)         → —
M12: (omitted)        → —

Product: 1.5 × 1.2 × 3 × 1 × 1 × 1.5 = 8.1
Value:   $100 × 8.1 = $810
```

**godaddy.icu** — .icu with trademark conflict, competing .com:

```
TLD: .icu (score 1), base = $5

M4: 2 words          → ×3
M3: 6 chars          → ×2
M7: "go"/"daddy"     → ×5
M8: informational     → ×1
M11: trademark match  → ×0.1
M5: pronounceable     → ×2
M10: .com active      → ×0.5
M1: (omitted)         → —
M12: (omitted)        → —

Product: 3 × 2 × 5 × 1 × 0.1 × 2 × 0.5 = 3.0
Value:   $5 × 3.0 = $15
```

---

## 5. TLD Score Table

54 TLDs ranked 1–10. All others default to 0.2.

| Score | TLDs |
|---|---|
| **10** | .com |
| **9** | .net |
| **8.5** | .io, .ai |
| **8** | .co, .de, .edu, .org, .xxx |
| **7.5** | .app, .it, .xyz |
| **7** | .us, .tv, .me, .cc, .to, .tech |
| **6.5** | .world |
| **6** | .eu, .sh, .ca, .inc, .wiki, .pro, .space, .shop, .online, .info, .in |
| **5** | .asia, .africa, .gg, .tel, .news, .site |
| **4.5** | .ltd |
| **4** | .cloud, .co.uk, .blog, .fun, .it.com, .sport, .studio, .live |
| **3.5** | .art |
| **3** | .network, .lgbt, .bio |
| **2** | .agency, .lol, .one, .biz |
| **1** | .icu |
| **0.2** | everything else |

---

## 6. Data Sources

| Module | Source | Key? | Cost | Limit | Attribution |
|---|---|---|---|---|---|
| M1 | rdap.org | No | Free | None | None |
| M7 | pytrends | No | Free | Unofficial | None |
| M7 (fallback) | Embedded word freq map | N/A | Free | N/A | None |
| M8 | Embedded CPC map | N/A | Free | N/A | None |
| M9 (primary) | Google CSE | Yes | Free | 100 queries/day | None |
| M9 (backup) | Brave Search | No | Free | ~1,000/month | None |
| M11 | USPTO TSDR | No | Free | None | None |
| M11 | EUIPO eSearch | No | Free | None | None |
| M12 | Wayback CDX | No | Free | None | None |
| M12 | Ahrefs DR (free) | No | Free | Undocumented | Required |
| M12 | OpenPageRank | Yes | Free | 30K/month, 60/min | None |

---

## 7. TLD Tier Weight Profiles

The TLD score determines which weight profile M15 uses for the multiplier aggregation. Higher TLD tiers favor scarcity factors; lower tiers favor commercial signals.

### Tier 10 (.com)

| Module | Weight |
|---|---|
| M4 Word count | 30 |
| M3 Length | 20 |
| M1 Age | 15 |
| M7 Popularity | 10 |
| M8 CPC | 10 |
| M12 History | 5 |
| M5 Pronounceability | 5 |
| M11 Trademark | 5 |
| M10 Cross-TLD | 0 |
| **Total** | **100** |

### Tier 8–9 (.net, .io, .ai, .co, .de, .org, .xxx)

| Module | Weight |
|---|---|
| M7 Popularity | 25 |
| M8 CPC | 20 |
| M4 Word count | 15 |
| M5 Pronounceability | 10 |
| M3 Length | 10 |
| M1 Age | 10 |
| M10 Cross-TLD | 5 |
| M11 Trademark | 3 |
| M12 History | 2 |
| **Total** | **100** |

### Tier 6–7.5 (.app, .xyz, .us, .tv, .me, .cc, .to, .tech, .world, etc.)

| Module | Weight |
|---|---|
| M7 Popularity | 30 |
| M8 CPC | 25 |
| M5 Pronounceability | 15 |
| M10 Cross-TLD | 10 |
| M4 Word count | 10 |
| M1 Age | 5 |
| M3 Length | 5 |
| **Total** | **100** |

### Tier 4–5 (.cloud, .blog, .news, .site, .asia, etc.)

| Module | Weight |
|---|---|
| M8 CPC | 30 |
| M7 Popularity | 25 |
| M10 Cross-TLD | 15 |
| M5 Pronounceability | 10 |
| M4 Word count | 8 |
| M1 Age | 5 |
| M3 Length | 5 |
| M11 Trademark | 2 |
| **Total** | **100** |

### Tier 1–3 (.icu, .biz, .one, .lol, .network, .art, etc.)

| Module | Weight |
|---|---|
| M8 CPC | 35 |
| M7 Popularity | 25 |
| M10 Cross-TLD | 20 |
| M5 Pronounceability | 10 |
| M4 Word count | 5 |
| M1 Age | 3 |
| M3 Length | 2 |
| **Total** | **100** |

### Tier 0.2 (default — all unlisted TLDs)

| Module | Weight |
|---|---|
| M8 CPC | 40 |
| M7 Popularity | 30 |
| M10 Cross-TLD | 20 |
| M5 Pronounceability | 5 |
| M4 Word count | 3 |
| M3 Length | 2 |
| **Total** | **100** |

### Brandable Fallback Profile

Activated when M6 returns `no_split`. Applied regardless of TLD tier.

| Module | Weight |
|---|---|
| M5 Pronounceability | 30 |
| M16 Brandability | 25 |
| M3 Length | 20 |
| M7 Popularity | 10 |
| M8 CPC | 5 |
| M10 Cross-TLD | 5 |
| M2 TLD | 3 |
| M11 Trademark | 2 |
| **Total** | **100** |

---

## 8. Output Schema

### Appraisal Response (JSON)

```json
{
  "domain": "car.com",
  "tld": "com",
  "tld_score": 10,
  "tld_base": 100,
  "estimated_value": 21600000,
  "range": {
    "low": 21600000,
    "high": 21600000
  },
  "confidence": {
    "label": "high",
    "completeness_ratio": 1.0,
    "missing_signals": []
  },
  "multiplier_product": 216000,
  "modules": {
    "m1_rdap": {
      "status": "success",
      "age_years": 27,
      "multiplier": 3
    },
    "m3_length": {
      "status": "success",
      "score": 98,
      "multiplier": 15
    },
    "m4_word_count": {
      "status": "success",
      "words": 1,
      "multiplier": 20
    },
    "m5_pronounceability": {
      "status": "success",
      "score": 98,
      "multiplier": 2
    },
    "m7_keyword_popularity": {
      "status": "success",
      "domain_score": 95,
      "source": "static",
      "multiplier": 8
    },
    "m8_cpc": {
      "status": "success",
      "tier": "elite",
      "match_word": "car",
      "multiplier": 5
    },
    "m11_trademark": {
      "status": "success",
      "conflict": false,
      "multiplier": 1
    },
    "m12_authority": {
      "status": "success",
      "authority_score": 95,
      "snapshots": 5000,
      "parked": false,
      "multiplier": 3
    }
  },
  "cache": {
    "hits": 4,
    "misses": 2,
    "rate": 0.67
  },
  "meta": {
    "appraisal_id": "a1b2c3d4",
    "timestamp": "2026-07-14T12:00:00Z",
    "version": "2.0.0",
    "duration_ms": 1234
  }
}
```

---

## 9. Configuration

### Config File (TOML)

```toml
[cache]
path = "~/.cache/ceche/cache.db"
fresh = false

[tld_base]
tier_10 = 100
tier_09 = 50
tier_08 = 50
tier_075 = 30
tier_07 = 30
tier_065 = 20
tier_06 = 20
tier_05 = 10
tier_045 = 10
tier_04 = 10
tier_035 = 5
tier_03 = 5
tier_02 = 5
tier_01 = 5
tier_00 = 2

[api_keys]
google_cse_key = ""
brave_search_key = ""
openpagerank_key = ""

[output]
format = "json"
include_raw_data = false

[ai]
provider = "none"
```

### Environment Variables

| Variable | Overrides |
|---|---|
| `CECHE_GOOGLE_CSE_KEY` | `api_keys.google_cse_key` |
| `CECHE_BRAVE_KEY` | `api_keys.brave_search_key` |
| `CECHE_OPR_KEY` | `api_keys.openpagerank_key` |
| `CECHE_CACHE_PATH` | `cache.path` |
| `CECHE_FRESH` | `cache.fresh` |

---

## 10. Caching Strategy

**Granularity:** Cache by term/segment, not by full domain. "insurance" is cached once and reused across all domains containing that word.

**Storage:** SQLite via Python's built-in `sqlite3`.

**Key format:** `{module}:{query_term}`

**TTL by source:**

| Source | TTL |
|---|---|
| RDAP | 24 hours |
| Keyword popularity | 7 days |
| CPC | 30 days |
| Search results | 7 days |
| Trademark | 30 days |
| Ahrefs DR | 7 days |
| Wayback | 30 days |
| OPR | 7 days |
| TLD table | 90 days |
| Static data | 365 days |

---

## 11. AI Enhancements (Optional)

Three areas where AI adds value beyond the deterministic scoring:

| Area | Module | Purpose | Enablement |
|---|---|---|---|
| Segmenter disambiguation | M6 | Resolve ambiguous word splits (portmanteaus, slang, brand names) | `[ai] enable_for_m6 = true` |
| Brandability refinement | M16 | Context-aware assessment of brand quality | `[ai] enable_for_m16 = true` |
| Multiplier calibration | M15 | Fit multiplier tables to known domain sales | `[ai] enable_for_calibration = true` |

AI is disabled by default. Each feature is independently configurable. The engine runs without any AI dependency.

---

## 12. Build Phases

### Phase 1 — Contracts & Domain Core (no infrastructure)

Deliverable: Pure Python package with all ABCs, data models, engine pipeline, and pure computation modules (M2, M3, M4, M5, M13, M15, M16).

Testable with 100% mock data — no network, no database, no external dependencies.

### Phase 2 — Infrastructure Adapters

Deliverable: One adapter at a time, each with unit tests (mocked) and integration tests (real API).

Order: RDAP → SQLite cache → CPC static data → Word frequency data → Google CSE → Ahrefs DR → Wayback → USPTO/EUIPO → Brave → pytrends → OPR

### Phase 3 — CLI Entry Point

Deliverable: `ceche appraise <domain>` command. Thin layer — argument parsing + output formatting. Uses dependency injection to wire adapters into the engine.

### Phase 4 — Web API Entry Point

Deliverable: FastAPI application with `/v1/appraise` endpoint, Swagger UI, health check, rate limiting, structured logging, and authentication.

Same engine, same adapters, different entry point.

---

## 13. Enterprise Standards

| Area | Standard |
|---|---|
| Language | Python 3.10+ |
| Architecture | Hexagonal (Ports & Adapters) |
| Web framework | FastAPI |
| CLI framework | Typer |
| Async HTTP | httpx |
| Linting | Ruff (all rules) |
| Type checking | mypy (strict) |
| Testing | pytest + pytest-asyncio |
| Test mocks | pytest-httpx (for HTTP adapters) |
| CI/CD | GitHub Actions |
| API spec | OpenAPI 3.0 (auto-generated) |
| Configuration | TOML + environment variables |
| Logging | Structured JSON |
| Error handling | Domain exceptions, never raw HTTP errors in domain layer |
| Secrets | .env (gitignored), never in code or config |

---

## 14. Domain Package Structure

```
ceche/
├── ceche/
│   ├── __init__.py
│   ├── __main__.py                    # python -m ceche
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── config.py                  # ConfigPort ABC + Config dataclass
│   │   ├── domain.py                  # DomainName value object
│   │   ├── engine.py                  # AppraisalEngine — orchestrates pipeline
│   │   ├── models.py                  # ModuleResult, AppraisalResult, etc.
│   │   ├── ports.py                   # All port ABCs (RDAPPort, CachePort, etc.)
│   │   ├── modules/
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # BaseModule ABC
│   │   │   ├── m01_rdap.py           # (pure: just defines port usage)
│   │   │   ├── m02_tld_table.py      # pure
│   │   │   ├── m03_length.py         # pure
│   │   │   ├── m04_word_count.py     # pure
│   │   │   ├── m05_pronounceability.py # pure
│   │   │   ├── m06_segmenter.py      # pure
│   │   │   ├── m07_keyword.py        # (pure: defines port usage)
│   │   │   ├── m08_cpc.py            # pure
│   │   │   ├── m09_search.py         # (pure: defines port usage)
│   │   │   ├── m10_cross_tld.py      # (pure: defines port usage)
│   │   │   ├── m11_trademark.py      # (pure: defines port usage)
│   │   │   ├── m12_authority.py      # (pure: defines port usage)
│   │   │   ├── m13_confidence.py     # pure
│   │   │   ├── m14_cache.py          # (pure: defines port usage)
│   │   │   ├── m15_pricing.py        # pure
│   │   │   └── m16_brandability.py   # pure
│   │   └── data/
│   │       ├── tld_scores.json
│   │       ├── cpc_keywords.json
│   │       ├── word_brandability.json
│   │       └── bigram_freq.json
│   │
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   └── sqlite_adapter.py
│   │   ├── rdap/
│   │   │   ├── __init__.py
│   │   │   └── rdap_adapter.py
│   │   ├── search/
│   │   │   ├── __init__.py
│   │   │   ├── google_cse_adapter.py
│   │   │   └── brave_adapter.py
│   │   ├── trademark/
│   │   │   ├── __init__.py
│   │   │   ├── uspto_adapter.py
│   │   │   └── euipo_adapter.py
│   │   ├── authority/
│   │   │   ├── __init__.py
│   │   │   ├── wayback_adapter.py
│   │   │   ├── ahrefs_adapter.py
│   │   │   └── opr_adapter.py
│   │   └── keyword/
│   │       ├── __init__.py
│   │       ├── pytrends_adapter.py
│   │       └── static_adapter.py
│   │
│   └── interfaces/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py               # Typer app
│       │   ├── commands/
│       │   │   ├── __init__.py
│       │   │   └── appraise.py      # appraise command
│       │   └── formatters.py        # JSON, table, pretty output
│       └── api/
│           ├── __init__.py
│           ├── app.py               # FastAPI app factory
│           ├── routes/
│           │   ├── __init__.py
│           │   └── v1.py            # /v1/appraise
│           └── schemas.py           # Pydantic request/response models
│
├── tests/
│   ├── conftest.py
│   ├── domain/
│   │   ├── test_engine.py
│   │   ├── test_domain.py
│   │   └── modules/
│   │       ├── test_m02_tld_table.py
│   │       ├── test_m03_length.py
│   │       ├── test_m04_word_count.py
│   │       ├── test_m05_pronounceability.py
│   │       ├── test_m06_segmenter.py
│   │       ├── test_m08_cpc.py
│   │       ├── test_m13_confidence.py
│   │       ├── test_m15_pricing.py
│   │       └── test_m16_brandability.py
│   ├── infrastructure/
│   │   ├── test_cache.py
│   │   ├── test_rdap.py
│   │   ├── test_google_cse.py
│   │   └── ...
│   └── interfaces/
│       ├── test_cli.py
│       └── test_api.py
│
├── docs/
│   ├── 01-architecture-overview.md
│   ├── 02-module-specifications.md
│   ├── 03-tld-score-table.md
│   ├── 04-scoring-and-valuation.md
│   ├── 05-caching-layer.md
│   ├── 06-configuration.md
│   ├── 07-ai-enhancements.md
│   ├── 08-cli-usage.md
│   ├── 09-build-order.md
│   └── 10-data-sources.md
│
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── ceche.toml
├── product-spec.md
└── README.md
```
