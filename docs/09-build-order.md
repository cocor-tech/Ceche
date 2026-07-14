# Build Order

Recommended implementation sequence, organized by dependency and risk.

## Phase 1: Core Infrastructure

**Goal:** Get the scaffolding working — a domain string goes in, a report comes out (even if most modules return null).

**Modules:**
- Project skeleton (`pyproject.toml`, package structure, entry point)
- CLI parser (`argparse`) with `ceche appraise <domain>` command
- Config loader (TOML)
- Domain parser (SLD/TLD extraction, punycode handling)
- M14 — Caching Layer (SQLite schema, get/set/get_or_compute/cleanup)
- M13 — Confidence Flag (aggregates statuses, placeholder logic)
- M15 — Pricing Module skeleton (basic multiplier multiplication, output formatting)
- M3 — Length Scorer (pure function, zero dependencies)
- Output formatters (JSON, table, pretty)

**Estimated effort:** Medium (2–3 days)

**Verification:** `ceche appraise example.com` runs, produces an output with TLD, length score, and $0 value (everything else is null).

---

## Phase 2: Word Analysis

**Goal:** Core NLP — segment the domain, score word count, score pronounceability.

**Modules:**
- M6 — Segmenter (DP word-break with wordfreq + google-10000-english)
- M4 — Word-Count Scorer (reads from M6)
- M5 — Pronounceability Scorer (vowel density + cluster + bigram)

**Dependencies:** `wordfreq`, `pyphen`, `nltk` (CMU dict)

**Estimated effort:** Medium (2–3 days)

**Verification:** `ceche appraise insurance.com` → shows "1 word, 10 chars, pronounceable". `ceche appraise fjfbfj.com` → shows "no split, unpronounceable". Length score still works.

---

## Phase 3: TLD & Registration Data

**Goal:** External data — registration status, age, TLD score.

**Modules:**
- M1 — RDAP Lookup (rdap.org API)
- M2 — TLD Score Table (static JSON, load and look up)
- M10 — Cross-TLD Check (reuses M1 for other TLDs + HTTP HEAD)

**Dependencies:** `httpx` (async HTTP)

**Estimated effort:** Low (1–2 days)

**Verification:** `ceche appraise example.com` → shows .com TLD score 10, registered since 1997. `ceche appraise notregisteredexample123xyz.com` → shows unregistered. Cross-TLD shows "example.com" exists for .com/.net/.org variants.

---

## Phase 4: Market Signals

**Goal:** The signals that make scores meaningful — keyword popularity, search presence, trademark checks.

**Modules:**
- M7 — Keyword Popularity (pytrends wrapper + static frequency fallback)
- M9 — Search Results Checker (Google CSE + Brave APIs)
- M11 — Trademark Check (USPTO + EUIPO scrapers)

**Dependencies:** `pytrends`, `httpx`, API signups (Google CSE, Brave Search)

**Estimated effort:** Medium-High (3–5 days)
- pytrends integration is fragile — expect 1–2 days for robust error handling
- USPTO/EUIPO scrapers need careful HTML parsing

**Verification:** `ceche appraise insurance.com` → shows high keyword popularity, high search results count, no trademark conflict. `ceche appraise google.com` → shows trademark conflict flag.

---

## Phase 5: Commercial & Authority Signals

**Goal:** CPC data, backlink/authority scoring.

**Modules:**
- M8 — CPC Scorer (static 5,000-keyword map, embed in codebase)
- M12 — Backlink/History/Authority (Wayback CDX API + Ahrefs DR + OpenPageRank)

**Dependencies:** `httpx`, signups (Ahrefs none needed, OPR needs account)

**Estimated effort:** Medium (2–3 days)
- Building the CPC keyword map from public sources takes time
- Ahrefs endpoint is simple (single GET)
- Wayback CDX API is well-documented

**Verification:** `ceche appraise carinsurance.com` → shows Elite CPC multiplier, high authority if registered. `ceche appraise sadmecry.com` → shows informational CPC, no authority (unregistered).

---

## Phase 6: Brandability & Valuation

**Goal:** Complete the engine with brandable domain support and calibrated dollar output.

**Modules:**
- M16 — Brandability Scorer (letter patterns, syllable flow, cross-TLD availability)
- M15 — Pricing Module (final integration of all multiplier curves)
- M13 — Confidence Flag (final logic: weighted completeness, per-TLD applicability rules)

**Estimated effort:** Medium (2–3 days)

**Verification:** `ceche appraise nekwasa.com` → shows brandable score, reasonable dollar estimate. Domain types produce distinct, realistic price ranges.

---

## Phase 7: Polish & Calibration

**Goal:** Production-ready output, error handling, documentation.

**Tasks:**
- Comprehensive error handling for all modules (timeouts, rate limits, parse errors)
- Retry logic with exponential backoff for external APIs
- M14 cache cleanup on startup
- `--fresh`, `--skip`, `--only` CLI flags
- Detailed logging (`-v`, `--verbose`)
- `README.md` with installation and usage instructions
- Calibrate multipliers against 10–20 known domain sales
- Unit tests for each module

**Estimated effort:** Medium (3–5 days)

**Verification:** Full end-to-end tests on 50+ domains covering all asset classes. Known sales produce reasonable valuations.

---

## Total Estimated Build Time

**Phase 1:** 2–3 days (core infrastructure)
**Phase 2:** 2–3 days (word analysis)
**Phase 3:** 1–2 days (TLD & registration)
**Phase 4:** 3–5 days (market signals)
**Phase 5:** 2–3 days (commercial & authority)
**Phase 6:** 2–3 days (brandability & valuation)
**Phase 7:** 3–5 days (polish & calibration)

**Total:** ~15–24 days for a working MVP with all 16 modules.

## Risk Points

| Risk | Module | Mitigation |
|---|---|---|
| pytrends breaks frequently | M7 | Static fallback tier — the system degrades gracefully |
| USPTO/EUIPO HTML changes | M11 | Cache aggressively (30-day TTL) to minimize calls |
| Google CSE quota exhausted | M9 | Brave backup tier + aggressive caching |
| Ahrefs rate-limit unknown | M12 | Cache at 7-day TTL, retry with backoff |
| Multiplier calibration | M15 | Start conservative (low multipliers), calibrate upward as sales data confirms |
| Brandable scoring too aggressive/weak | M16 | Rule-based first, AI refinement as option |
