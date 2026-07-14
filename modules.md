# Ceche — Module Development Milestones

13 milestones, 2 sub-modules each. Build order optimized for dependency resolution and earliest-possible end-to-end testing.

---

## Milestone 1 — Project Scaffold & Core Infrastructure

### 1.1 — Project Scaffold

**Deliverable:** Runnable Python package with all tooling configured.

- Initialize `pyproject.toml` with all dependencies
- Configure Ruff (linter + formatter) and mypy (strict mode)
- Set up `pytest` + `pytest-asyncio` with `conftest.py`
- Create GitHub Actions CI workflow (lint → typecheck → test)
- Create `.env.example`, `.gitignore`, `ceche.toml` default config
- Implement `config.py` — TOML loader with environment variable overrides
- Verify: `python -m ceche --version` prints version

**Dependencies:** None.

### 1.2 — Domain Parser & Value Objects

**Deliverable:** Domain parsing with full edge case coverage.

- `DomainName` value object: parse SLD + TLD from any domain string
- Punycode/IDN decoding (`xn--ls8h.com` → normalized form)
- Strip protocol, path, port, www prefix (handle full URLs gracefully)
- Validate TLD against IANA list (or just extract the last dot segment)
- Unit tests: `example.com`, `topinsurance.co`, `xn--ls8h.com`, `sub.domain.co.uk`, `http://example.com/path?q=1`
- `DomainName.tld` and `DomainName.sld` properties

**Dependencies:** 1.1.

---

## Milestone 2 — Static Data Modules

### 2.1 — TLD Score Table (M2)

**Deliverable:** Module that assigns a 1–10 score to any TLD.

- Create `ceche/domain/data/tld_scores.json` with 54 custom scores + 0.2 default
- Implement `M2TLDTable` module: reads JSON, looks up TLD, returns score
- Weight profile selection: TLD score maps to a profile identifier string
- Unit tests: `.com` → 10, `.net` → 9, `.icu` → 1, `.nonexistent` → 0.2
- All data files are module-level constants, loaded once on first import

**Dependencies:** 1.1, 1.2.

### 2.2 — CPC / Commercial Intent Scorer (M8)

**Deliverable:** Module that assigns a CPC tier to any domain word.

- Collect ~5,000 high-CPC keywords from public sources into `ceche/domain/data/cpc_keywords.json`
- Define CPC tiers: Elite (×5), High (×3), Medium-High (×2.5), Medium (×2), Low (×1.5), Informational (×1), None (×1)
- Implement `M8CPC` module: look up each word from M6 segmentation, return highest tier
- Unit tests: `"insurance"` → Elite, `"blue"` → Informational, `"sdfjk"` → None
- If M6 returns no_split, return None (brandable profile handles it)

**Dependencies:** 1.1, 1.2. (Does not require M6 — reads word list from context, not from M6 directly.)

---

## Milestone 3 — Word Analysis Engine

### 3.1 — Segmenter (M6) & Word-Count Scorer (M4)

**Deliverable:** Core NLP — DP word-break segmentation and word count scoring.

**M6 — Segmenter:**
- Dynamic programming word-break over common English word list
- Word frequency weighting from wordfreq + google-10000-english
- Return top 3 segmentations ranked by total word probability
- If no valid split, return `status: "no_split"` (triggers brandable fallback)
- Hyphen handling: split on hyphens, score each segment
- Unit tests: `"insurance"` → 1 word, `"topinsurance"` → 2 words, `"nekwasa"` → no_split
- Embedded word list data file for zero external dependency at runtime

**M4 — Word-Count Scorer:**
- Read word count from M6's winning segmentation
- Implement exponential penalty: `100 × e^(-0.5×(words-1))`
- If M6 returns no_split, return None
- Unit tests: 1 word → 100, 2 words → 60, 3 words → 35

**Dependencies:** 1.1, 1.2. (M4 reads M6's output from shared context.)

### 3.2 — Length Scorer (M3) & Pronounceability Scorer (M5)

**Deliverable:** Two pure modules for domain surface-quality assessment.

**M3 — Length Scorer:**
- Implement inverted sigmoid: `100 × (1 - 1/(1 + e^(-0.8×(len-5))))`, clamped [0, 100]
- Hyphens counted in length
- Punycode decoded before counting
- Score → multiplier mapping table
- Unit tests: 3 chars → 98, 6 chars → 75, 10 chars → 25, 15 chars → ~3

**M5 — Pronounceability:**
- Vowel density metric (bell curve centered at 0.40, weight 40%)
- Consonant cluster penalty (max consecutive consonants, weight 30%)
- Bigram frequency (embedded frequency table, weight 30%)
- 1–2 char strings: fixed at 100
- Unit tests: `"yotop"` → high, `"fjfbfj"` → low, `"abc"` → medium

**Dependencies:** 1.1, 1.2. M5 uses embedded bigram data.

---

## Milestone 4 — Port Definitions & Abstraction Layer

### 4.1 — All Port Interfaces (Abstract Base Classes)

**Deliverable:** Complete set of domain-layer port ABCs. Zero implementations.

- `RDAPPort`: `async lookup(domain: DomainName) -> RDAPResult`
- `CachePort`: `async get(key)`, `async set(key, value, ttl)`, `get_or_compute(key, ttl, fn)`
- `SearchPort`: `async search(query: str) -> SearchResult`
- `TrademarkPort`: `async check(term: str) -> TrademarkResult`
- `AuthorityPort`: `async get_authority(domain: DomainName) -> AuthorityResult`
- `KeywordPopularityPort`: `async get_popularity(term: str) -> KeywordResult`
- `ConfigPort`: `load() -> Config`
- Every port method is async, returns typed dataclass, raises domain exceptions on error
- Unit tests: Mock implementations for every port (used by engine tests)

**Dependencies:** 1.1, 1.2.

### 4.2 — Base Module & Engine Pipeline Definition

**Deliverable:** Module interface + engine skeleton with dependency graph.

- `BaseModule` ABC: `async run(context: AppraisalContext) -> ModuleResult`
- `ModuleResult` dataclass: `value`, `confidence`, `data`, `status`
- `AppraisalContext`: shared dict for passing data between modules
- Engine dependency graph: M6 → M4, M7, M8, M11. M1 → M12. All else independent.
- Engine wiring: receives port implementations via constructor injection
- Unit tests: Engine runs a mock pipeline (all ports mocked) and produces a correct `AppraisalResult`

**Dependencies:** 4.1.

---

## Milestone 5 — Caching & Registration

### 5.1 — SQLite Cache Adapter (M14)

**Deliverable:** Working cache with correct TTL enforcement.

- Implement `SQLiteCacheAdapter` implementing `CachePort`
- SQLite schema: `cache(key, value, ttl, created_at, expires_at)` with index on `expires_at`
- `get_or_compute(key, ttl, fn)`: check cache → if miss, call fn → store → return
- Auto-cleanup on startup and every 100 writes
- Unit tests: set then get, miss on missing key, expired key returns None, cleanup purges correctly
- Integration test: write 1000 entries, verify file size and query performance

**Dependencies:** 4.1, 4.2.

### 5.2 — RDAP Adapter (M1)

**Deliverable:** Working RDAP lookup with caching.

- Implement `RDAPAdapter` implementing `RDAPPort`
- Query `https://rdap.org/domain/{domain}` via httpx
- Parse RDAP JSON response: registration status, creation date, expiry date, registrar
- Handle unregistered domains (RDAP returns 404 → return `not_found` status)
- Handle errors, timeouts, malformed responses
- Wrap with cache: key = `rdap:{domain}`, TTL = 24 hours
- Unit tests: mock httpx responses for registered + unregistered + error
- Integration test (optional): query a known registered domain

**Dependencies:** 4.1, 4.2, 5.1.

---

## Milestone 6 — Market Signal Adapters

### 6.1 — Keyword Popularity Adapters (M7)

**Deliverable:** Tiered keyword popularity lookup with fallback.

- `pytrendsAdapter`: wraps pytrends library for Google Trends data
- `StaticKeywordAdapter`: embedded ~10,000 word frequency map
- Fallback chain: pytrends → static → ×1.0
- Cache: key = `kw:{term}`, TTL = 7 days
- Handle pytrends rate limits: catch exceptions, fall to static
- Unit tests: mock pytrends responses, test fallback chain
- Integration test (optional): query one real term via pytrends

**Dependencies:** 4.1, 4.2, 5.1.

### 6.2 — Search Results Adapters (M9)

**Deliverable:** Search result lookup with Google CSE and Brave fallback.

- `GoogleCSEAdapter`: query Google Custom Search JSON API
- `BraveAdapter`: query Brave Search API
- Fallback chain: Google CSE → Brave → None
- Parse search result count and top snippets
- Detect competing TLD variants in search results
- Cache: key = `search:{domain}`, TTL = 7 days
- Unit tests: mock httpx responses for both APIs
- Integration test (optional): query one real domain via Google CSE

**Dependencies:** 4.1, 4.2, 5.1.

---

## Milestone 7 — Risk & Competition Adapters

### 7.1 — Trademark Adapters (M11)

**Deliverable:** Trademark conflict detection.

- `USPTOAdapter`: scrape USPTO TSDR for trademark matches
- `EUIPOAdapter`: scrape EUIPO eSearch for trademark matches
- Conflict severity: none, partial (word is part of a mark), exact (full string match)
- Cache: key = `tm:{term}`, TTL = 30 days
- Handle HTML structure changes gracefully (robust parsing)
- Unit tests: mock HTML responses, test parsing logic
- Note: Integration tests may fail if site structure changes — design tests to verify parsing, not network

**Dependencies:** 4.1, 4.2, 5.1.

### 7.2 — Cross-TLD Check (M10)

**Deliverable:** Competing TLD variant detection.

- Reuses `RDAPPort` to query same SLD on .com, .net, .org, .co, .io, .app, .dev, .xyz
- HTTP HEAD to detect parked vs live content
- If appraising a .com: no penalty (canonical)
- If non-.com and .com variant is active: penalty multiplier ×0.5
- Unit tests: mock RDAP for multiple TLDs, verify correct penalty application

**Dependencies:** 4.1, 4.2, 5.1, 5.2.

---

## Milestone 8 — Authority & Branding

### 8.1 — Wayback Machine Adapter

**Deliverable:** Content history and parked detection.

- Query `https://archive.org/wayback/available?url={domain}`
- Parse snapshot count, earliest/latest dates
- Parked detection: 0 snapshots after 6 months registration → parked
- Cache: key = `wayback:{domain}`, TTL = 30 days
- Unit tests: mock CDX API responses
- Integration test (optional): query a well-known domain

**Dependencies:** 4.1, 4.2, 5.1.

### 8.2 — Authority Adapters (Ahrefs DR + OpenPageRank)

**Deliverable:** Blended authority score.

- `AhrefsDRAdapter`: query `GET https://api.ahrefs.com/v3/public/domain-rating-free?target={domain}`
- `OPRAdapter`: query `POST https://openpagerank.keywordseverywhere.com/v1/domains/bulk` with Bearer token
- Blended score: `ahrefs_norm × 0.6 + opr_norm × 0.4`
- If only one source available: use it × 0.8 (penalized)
- If neither: return None
- Cache: key = `auth:{domain}`, TTL = 7 days
- Unit tests: mock both API responses
- Integration test (optional): query a known domain

**Dependencies:** 4.1, 4.2, 5.1.

## Milestone 9 — Brandability & Aggregation

### 9.1 — Brandability Scorer (M16)

**Deliverable:** Brandable domain assessment for non-dictionary strings.

- Syllable flow analysis
- Letter pattern scoring (-ify, -ly, -ex, -io, -o, -a endings)
- Bigram/trigram frequency for memorability
- Cross-TLD availability for startup naming value
- Only activated when M6 returns no_split
- Unit tests: `"nekowi"` → high, `"yotop"` → medium, `"fjfbfj"` → low

**Dependencies:** 1.1, 1.2, 3.1 (M6 for no_split detection).

### 9.2 — Confidence Flag (M13)

**Deliverable:** Completeness tracking across all modules.

- Track status of every module call during an appraisal
- Compute `completeness_ratio = modules_with_data / applicable_modules`
- Determine applicable modules per domain type (registered → include M1/M12, unregistered → exclude)
- Compute confidence range for M15
- Unit tests: all modules success, some modules null, unregistered domain, rate-limited scenario

**Dependencies:** 4.2 (runs after all other modules in the pipeline).

---

---

## Milestone 10 — Pricing Module (M15)

### 10.1 — Pricing Module

**Deliverable:** Dollar valuation with multiplier math.

- Read all module results from context
- Select weight profile based on TLD score tier (or brandable fallback if M6 = no_split)
- Look up multiplier for each module's score
- Compute: `tld_base × m4_mult × m3_mult × m7_mult × ...`
- Apply confidence range from M13
- Format `AppraisalResult` with breakdown, range, confidence metadata
- Unit tests: full-pipeline mock with known inputs → verify correct dollar output
- Verify: `abc.com` → $4,320,000, `car.com` → $21,600,000

**Dependencies:** 4.2, 9.2.

### 10.2 — Engine Integration & E2E Tests

**Deliverable:** Fully wired engine with all modules, tested end-to-end.
- Wire all 16 modules into the engine pipeline
- Module dependency resolution: M6 → M4/M7/M8/M11. M1 → M12. Others independent.
- Concurrency: modules without dependencies run in parallel via asyncio.gather()
- Error isolation: one module failure never crashes the pipeline
- Graceful degradation for unregistered domains (M1/M12 skipped)
- E2E tests with all adapters mocked: verify full pipeline produces correct `AppraisalResult`
- Known-value tests: `abc.com` mock data → $4,320,000, `car.com` → $21,600,000, `nekwasa.com` → ~$1,500

**Dependencies:** All milestones 1–9.

---

## Milestone 11 — Entry Points & Distribution

### 11.1 — CLI Entry Point (Typer)

**Deliverable:** Production-ready command-line interface.

- `ceche appraise <domain>` — single domain
- `ceche appraise <file>` — batch from file
- `ceche appraise <domain1> <domain2>` — multiple domains
- Flags: `--fresh`, `--format json|table|pretty`, `--include-raw`, `--skip`, `--only`, `--quiet`
- Output formatters: JSON dump, terminal table (rich), human-readable pretty
- Dependency injection: wire all infrastructure adapters, inject into engine
- Handle SIGINT gracefully (print partial results)
- Proper exit codes (0 success, 1 partial, 2 error, 3 config error)
- Unit tests: mock engine, verify output formatting
- Integration test: run against a real domain with `--fresh`

**Dependencies:** All milestones 1–10.

### 11.2 — Web API Entry Point (FastAPI)

**Deliverable:** Production-ready REST API.

- FastAPI application with factory pattern
- `POST /v1/appraise` — accepts `{"domain": "example.com"}`, returns full appraisal
- `GET /v1/appraise/{domain}` — alternative GET endpoint for simple queries
- `GET /v1/health` — health check (cache status, API key validity)
- Pydantic request/response models matching the domain dataclasses
- OpenAPI 3.0 spec auto-generated (Swagger UI at `/v1/docs`)
- Rate limiting per IP (configurable)
- Structured JSON logging (request ID, duration, module statuses)
- CORS configuration for web client access
- Startup: validate config, verify cache directory, preload static data
- Unit tests: FastAPI TestClient with mocked engine
- Integration test: start application, POST a domain, verify full response cycle

**Dependencies:** All milestones 1–10.

---

## Milestone 12 — Engine Orchestrator (M17)

### 12.1 — AppraisalEngine Pipeline

**Deliverable:** Central coordinator that runs all 16 modules in dependency-respecting phases.

- Domain parser: split `example.com` → SLD=`example`, TLD=`com`; handle punycode, strip protocols, lowercase
- Dependency graph with 6 execution phases:
  - Phase 1 (parallel): M1 RDAP, M2 TLD table, M6 segmenter
  - Phase 2 (sequential after M6): M3 length, M4 word count, M5 pronounceability
  - Phase 3 (parallel, needs M6 words): M7 keyword, M8 CPC, M11 trademark
  - Phase 4 (parallel, needs M1): M9 search, M10 cross-TLD, M12 authority
  - Phase 5 (conditional): M16 brandability ONLY if M6 = `no_split`
  - Phase 6 (final): M13 confidence, M15 pricing
- Shared context dict: each module reads from / writes to `words`, `mult_*`, `registered`, `age_years`, `weight_profile`, `m6_status`, `completeness_ratio`
- Brandable fallback: if M6 = `no_split`, skip M4/M7/M8, activate M16
- Error isolation: `try/except` per module, `ERROR` status never crashes the pipeline
- Graceful degradation: unregistered → skip M1/M12 multiplier contributions, M13 accounts for reduced available weight
- Constructor injection: receives all port/adapter implementations at init time
- Single method: `async def appraise(domain: str) -> AppraisalResult`

**Dependencies:** All milestones 1–11.

### 12.2 — AppraisalResult & Context Wiring

**Deliverable:** Typed output model and complete context wiring.

- `AppraisalResult` dataclass: `domain`, `estimated_value`, `range_low`, `range_high`, `confidence`, `tld_score`, `weight_profile`, `modules` (per-module breakdown dict)
- Context key contracts:
  - **Produced by M1:** `registered`, `age_years`
  - **Produced by M2:** `tld_score`, `weight_profile`
  - **Produced by M6:** `words`, `word_count`, `m6_status`
  - **Produced by M3–M12:** `mult_{module_name}` (multiplier float)
  - **Produced by M13:** `completeness_ratio`, `confidence_label`
  - **Consumed by M15:** `weight_profile`, all `mult_*`, `completeness_ratio`
- Engine writes module results back into context after each phase
- E2E tests: mock all adapters, verify known values (`abc.com` → ~$4.3M, `car.com` → ~$21.6M, `nekwasa.com` → ~$1,500)

**Dependencies:** All milestones 1–11.

---

## Milestone 13 — Entry Points & Distribution (M18)

### 13.1 — CLI Entry Point (Typer)

**Deliverable:** Production-ready command-line interface.

- `ceche appraise <domain>` — single domain
- `ceche appraise <file>` — batch from file
- `ceche appraise <domain1> <domain2>` — multiple domains
- Flags: `--fresh`, `--format json|table|pretty`, `--include-raw`, `--skip`, `--only`, `--quiet`
- Output formatters: JSON dump, terminal table (rich), human-readable pretty
- Dependency injection: wire all infrastructure adapters, inject into engine
- Handle SIGINT (print partial results)
- Exit codes: 0 success, 1 partial failure, 2 error, 3 config error
- Unit tests: mock engine, verify output formatting
- Integration test: run against a real domain with `--fresh`

**Dependencies:** All milestones 1–12.

### 13.2 — Web API Entry Point (FastAPI)

**Deliverable:** Production-ready REST API.

- FastAPI application with factory pattern
- `POST /v1/appraise` — `{"domain": "example.com"}`, returns full AppraisalResult
- `GET /v1/appraise/{domain}` — alternative GET endpoint
- `GET /v1/health` — cache status, API key validity
- Pydantic request/response models matching domain dataclasses
- OpenAPI 3.0 auto-generated (Swagger UI at `/v1/docs`)
- Rate limiting per IP (configurable)
- Structured JSON logging (request ID, duration, module statuses)
- CORS for web client access
- Startup: validate config, verify cache, preload static data
- Unit tests: FastAPI TestClient with mocked engine
- Integration test: full POST /v1/appraise cycle

**Dependencies:** All milestones 1–12.

---

## Summary

| Milestone | Focus | Modules Covered |
|---|---|---|
| 1 | Scaffold + domain parser | — |
| 2 | Static data | M2, M8 |
| 3 | Word analysis | M6, M4 |
| 4 | Surface quality | M3, M5 |
| 5 | Ports + engine skeleton | All (interfaces only) |
| 6 | Cache + RDAP | M14, M1 |
| 7 | Market signals | M7, M9 |
| 8 | Risk & competition | M11, M10 |
| 9 | Authority & branding | M12, M16 |
| 10 | Confidence + pricing | M13, M15 |
| 11 | Engine orchestrator | M17 |
| 12 | CLI entry point | M18 (CLI) |
| 13 | Web API entry point | M18 (API) |

Each milestone is independently testable. Mock data is available from milestone 5 onward for any module not yet implemented.
