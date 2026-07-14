# Module Specifications

Each module is a self-contained scorer that evaluates one dimension of a domain. Every module implements a common interface:

```python
class BaseModule(ABC):
    name: str
    async def run(self, domain: str, context: dict) -> ModuleResult:
        ...
```

`ModuleResult` contains:
- `value`: float or None — the raw output (multiplier for M15, internal score for intermediate)
- `confidence`: float 0–1
- `data`: dict — raw data returned (for reports)
- `status`: str — `success` | `quota_exceeded` | `not_found` | `error` | `skipped`

---

## M1 — RDAP / WHOIS Lookup

**Purpose:** Registration status, domain age, registrar, expiry date.

**Source:** RDAP (Registration Data Access Protocol) — ICANN-mandated free successor to WHOIS.

**Endpoint:** `https://rdap.org/domain/{domain}` — no key, no signup.

**Output:**
- `registered`: bool
- `creation_date`: ISO date or null
- `expiry_date`: ISO date or null
- `registrar`: string or null
- `age_years`: float — only if registered

**Module statuses:**
- `success`: RDAP returned registration data
- `not_found`: domain is unregistered (RDAP 404)
- `error`: RDAP unavailable or malformed response

**Cache TTL:** 24 hours

---

## M2 — TLD Score Table

**Purpose:** Assigns a 1–10 score to the TLD based on market value.

**Source:** Static JSON file (`ceche/data/tld_scores.json`) — 54 TLDs with custom scores, all others default to 0.2.

**Output:**
- `tld_score`: float (1–10 or 0.2 default)
- `tld`: string (normalized lowercase)

**Weight profile selection:** The TLD score determines which weight profile M15 uses. Higher scores favor scarcity (length, word count), lower scores favor commercial signals (CPC, popularity).

**Cache TTL:** 90 days (static data, rarely changes)

---

## M3 — Character Length Scorer

**Purpose:** Scores the SLD (second-level domain) length on a curve. Shorter scores higher.

**Formula:** Inverted sigmoid centered at 5 characters:
```
score = 100 × (1 - 1 / (1 + e^(-0.8 × (len - 5))))
```
Clamped to [0, 100].

| Length | Score |
|---|---|
| 1-3 | 99–98 |
| 4 | 92 |
| 5 | 85 |
| 6 | 75 |
| 7 | 62 |
| 8 | 48 |
| 9 | 35 |
| 10 | 25 |
| 12 | 12 |
| 15+ | ~3 |

**Source:** Pure local computation. No external dependency.

**Edge cases:**
- Hyphens: counted as characters (penalizes hyphenated domains)
- Numeric: treated as letters
- IDN/punycode: decode to readable form before counting
- Empty SLD: return 0

**Output multiplier mapping (used by M15):**
- Score >= 95 → ×15
- Score >= 75 → ×8
- Score >= 50 → ×2
- Score >= 25 → ×1.2
- Score < 25 → ×1.0

---

## M4 — Word-Count Scorer

**Purpose:** Penalizes domains with multiple words. One word scores highest.

**Dependency:** Reads `word_count` from M6's winning segmentation.

**Formula:** Exponential penalty curve:
```
score = 100 × e^(-0.5 × (words - 1))
```

| Words | Score |
|---|---|
| 1 | 100 |
| 2 | 60 |
| 3 | 35 |
| 4 | 20 |
| 5+ | 5 |

**Edge cases:**
- M6 returns `no_split` → M4 returns null (no word count, brandable profile activates instead)
- Hyphenated domains: M6 splits on hyphens, so "top-insurance" = 2 words

**Output multiplier mapping (used by M15):**
- 1 word → ×20
- 2 words → ×3
- 3 words → ×1.5
- 4+ words → ×1.0
- null → omitted from multiplier product

---

## M5 — Pronounceability Scorer

**Purpose:** Rates how easily a string can be spoken aloud, independent of dictionary meaning. Separates "yotop" (sayable) from "fjfbfj" (not).

**Three metrics combined:**

1. **Vowel density** (40% weight)
   - `vowel_ratio = vowel_count / total_chars`
   - Ideal range: 0.30–0.55
   - Too low: `fjfbfj` (0 vowels → score 0)
   - Too high: `aeiou` (>0.80 → unnatural, penalized)
   - Curve: bell curve centered at 0.40

2. **Consonant cluster penalty** (30% weight)
   - Max consecutive consonants
   - 1–2: no penalty (100)
   - 3: mild penalty (70)
   - 4: heavy penalty (30)
   - 5+: near 0
   - Exceptions: common English clusters like "str", "ght", "nds" get a small pass

3. **Letter-pair (bigram) frequency** (30% weight)
   - Pre-computed bigram frequency table from English text
   - "th", "er", "in", "ou" → high score
   - "fj", "xk", "zq" → low score
   - Average across all adjacent pairs in the string

**Final score:** `(vowel_score × 0.4 + cluster_score × 0.3 + bigram_score × 0.3)`, clamped to [0, 100].

**Source:** Pure Python logic. Bigram frequency table embedded as static data.

**Edge cases:**
- 1–2 char strings: fixed at 100 (too short to be unpronounceable)
- Hyphens: treated as consonants for vowel ratio, ignored for bigram

**Output multiplier mapping:**
- Score >= 90 → ×2.0
- Score >= 70 → ×1.5
- Score >= 40 → ×1.2
- Score < 40 → ×1.0

---

## M6 — Segmenter (Multi-Way Split)

**Purpose:** Breaks a domain string into every valid 1-, 2-, and 3+-word reading, scores each candidate, and surfaces the strongest plus alternates.

**Algorithm:** Dynamic programming word-break over a common English word list (seeded from google-10000-english + wordfreq word frequency weights).

**Input:** SLD only (e.g., "beastar" from "beastar.com")

**Output:**
- `winner`: list of words (the best segmentation)
- `word_count`: int
- `alternates`: list of alternative segmentations (top 3)
- `confidence`: float — how confident the algorithm is in the winner

**No-split handling:** If no valid dictionary split is found (brandable coinage), M6 returns `status: "no_split"`. This routes the domain through M16 (Brandability) instead of M4 and M7.

**Examples:**
- `insurance` → `["insurance"]` (1 word, high confidence)
- `topinsurance` → `["top", "insurance"]` (2 words)
- `beastar` → `["beast", "star"]` or `["be", "a", "star"]` — DP picks highest weighted

**Source:** `wordfreq` Python package + google-10000-english word list.

---

## M7 — Keyword Popularity Lookup

**Purpose:** For each word in M6's winning segmentation, get a relative search interest score (0–100) and multiplier.

**Source:** Tiered fallback system:

| Tier | Source | Reliability |
|---|---|---|
| 1 | M14 cache | 100% |
| 2 | pytrends (Google Trends) | ~60% (breaks often) |
| 3 | Static keyword frequency map | ~80% |

**Static fallback:** Pre-built frequency map of ~10,000 English words seeded from wordfreq/Google Books Ngram.

**Scoring:**
- Each word gets 0–100 based on relative search frequency
- Domain score = **max** of its word scores
- If no words found (M6 failed): return null

**Output multiplier mapping:**
- Domain score >= 90 → ×8
- Domain score >= 70 → ×5
- Domain score >= 50 → ×3
- Domain score >= 30 → ×2
- Domain score >= 10 → ×1.5
- Domain score < 10 or null → ×1.0

**Cache TTL:** 7 days

---

## M8 — CPC / Commercial-Intent Scorer

**Purpose:** Assigns a commercial-intent multiplier based on known CPC tiers of the domain's words.

**Source:** Static JSON file of ~5,000 high-CPC keywords embedded in the codebase. No API.

**Tier system:**

| Tier | CPC Range | Example Keywords | Multiplier |
|---|---|---|---|
| Elite | $50–$100+ | insurance, loans, mesothelioma, lawyer | ×5 |
| High | $20–$50 | mortgage, credit card, attorney, rehab | ×3 |
| Medium-High | $10–$20 | hosting, vpn, casino, betting | ×2.5 |
| Medium | $3–$10 | marketing, seo, plumber, roofing | ×2 |
| Low | $1–$3 | yoga, cooking, travel, blog | ×1.5 |
| Informational | $0–$1 | how, what, help, guide, sad | ×1 |
| None | 0 | gibberish, brand coinage | ×1 |

**Logic:**
- Look up each word from M6's segmentation in the CPC map
- Take the **highest** tier found (one high-CPC word is enough)
- If no words found (M6 failed): return ×1

**Cache TTL:** 30 days

---

## M9 — Search Results Checker

**Purpose:** Searches the full domain string and reads the pattern: many related results → established concept; scattered → brandable coinage; competing TLD variant actively ranking → conflict flag.

**Source:**
- Primary: Google Programmable Search Engine (100 free queries/day)
- Backup: Brave Search API (~1,000 free queries/month)

**Output:**
- `result_count`: int or null
- `top_snippets`: list of strings (first 3 result titles/snippets)
- `competing_tld`: bool — is a different TLD variant ranking on page 1?

**Multiplier mapping:**
- Result count >= 10,000 → ×5
- Result count >= 1,000 → ×3
- Result count >= 100 → ×2
- Result count >= 10 → ×1.3
- Result count < 10 or null → ×1.0

**Cache TTL:** 7 days

---

## M10 — Cross-TLD Check

**Purpose:** Checks whether the same SLD string exists on other common TLDs (.com, .net, .org, .co, .io, .app, .dev, .xyz). Flags if a stronger TLD variant is parked or active.

**Source:** Reuses M1's RDAP lookup against each candidate TLD + HTTP HEAD to detect parked vs live content.

**Logic:**
- If .com variant exists and is active → minor flag for non-.com domains
- If same string on multiple strong TLDs → moderate flag (divided brand presence)
- If the canonical .com is the domain being appraised → no flag (penalty = 0)
- No results (unregistered across all TLDs) → no flag

**Multiplier:** ×1 normally. ×0.5 if competing .com is strong and domain is non-.com.

---

## M11 — Trademark Check

**Purpose:** Flags live trademark conflicts on the segmented words or full string.

**Source:**
- USPTO TSDR (free, no key) — US trademarks
- EUIPO eSearch (free, no key) — EU trademarks
- WIPO Global Brand Database (manual search, free)

**Logic:**
- Look up each word from M6's segmentation in trademark databases
- Exact match on a live trademark class → conflict flag
- Partial match (word is part of a registered mark) → weaker flag
- Dictionary words are generally clean unless the domain exactly mirrors a known brand

**Multiplier:**
- No conflict → ×1
- Weak conflict (partial word match) → ×0.5
- Strong conflict (exact brand match) → ×0.1
- Same owner as trademark holder (e.g., trademark.com) → ×1

**Cache TTL:** 30 days

---

## M12 — Backlink / History / Age Checker

**Purpose:** Only activates for registered domains. Returns null cleanly for unregistered.

**Three sub-signals:**

1. **Age** — from M1 RDAP creation date (already computed)
2. **Content history** — Wayback Machine CDX API
   - Total snapshot count
   - Earliest snapshot date
   - Gap analysis (parked detection)
3. **Authority** — Blended from two sources:
   - Ahrefs free DR endpoint (no key): `GET https://api.ahrefs.com/v3/public/domain-rating-free?target=<domain>`
   - OpenPageRank (free 30K/mo, requires signup): OPR score 0–10 + referring domains

**Parked domain detection:**
```
0 snapshots and registered ≥6 months → parked_flag = true, multiplier ×0.5
1–10 snapshots → likely parked, ×0.7
10–100 → minimal history, ×1.2
100+ → active site, ×2
1000+ over multiple years → established, ×3
unregistered → null
```

**Blended authority score:**
```
If both Ahrefs DR + OPR available:
  ahrefs_norm = ahrefs_dr / 100
  opr_norm = opr_score / 10
  authority = ahrefs_norm × 0.6 + opr_norm × 0.4

If only one available:
  authority = available_source × 0.8 (penalized)

If neither available:
  authority = null
```

**Multiplier output:**
- authority × snapshot_multiplier combined, calibrated to range ×1–×5

**Cache TTL:** Ahrefs/OPR: 7 days. Wayback: 30 days.

---

## M13 — Confidence / Data-Completeness Flag

**Purpose:** Tags every appraisal with which modules returned real data vs hit a quota or returned null. A missing signal is never silently scored as zero.

**Logic:**
- Each module call returns a status alongside its value
- M13 aggregates all statuses into:
  - `applicable_modules`: total count of modules that should have data
  - `modules_with_data`: count that returned `success`
  - `completeness_ratio`: modules_with_data / applicable_modules
  - `confidence_label`: `high` (≥0.9) | `medium` (≥0.7) | `low` (≥0.5) | `very_low` (<0.5)
  - `missing_signals`: list of modules that returned null/quota

**Output:**
- Used in M15 to widen the price range when confidence is low
- Displayed in the report so users know which signals were missing

**Source:** Pure local logic. No external dependency.

---

## M14 — Caching Layer

**Purpose:** Caches lookups by term/segment, not by full domain. Fragments like "top", "shop", "get" repeat across thousands of queries.

**Storage:** SQLite (`ceche/cache/cache.db`)

**Schema:**
```sql
CREATE TABLE cache (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    ttl         INTEGER NOT NULL,
    created_at  INTEGER NOT NULL,
    expires_at  INTEGER NOT NULL
);
CREATE INDEX idx_expires ON cache(expires_at);
```

**Key format:** `{module_name}:{query_term}`

**TTL per module:**

| Module | TTL | Rationale |
|---|---|---|
| M1 RDAP | 24 hours | Registration status stable |
| M2 TLD scores | 90 days | Static data |
| M6 Segmentations | 30 days | Word lists are stable |
| M7 Keyword popularity | 7 days | Trends shift weekly |
| M8 CPC | 30 days | CPC is stable |
| M9 Search results | 7 days | SERPs change |
| M11 Trademark | 30 days | New filings daily |
| M12 Ahrefs | 7 days | Authority changes slowly |
| M12 Wayback | 30 days | Snapshots accumulate slowly |
| M12 OPR | 7 days | Monthly crawl updates |

See `05-caching-layer.md` for full documentation.

---

## M15 — Pricing / Valuation Module

**Purpose:** Converts all module outputs into a dollar estimate with confidence range.

**Formula:**
```
final_value = tld_base × multiplier_m4 × multiplier_m3 × multiplier_m7 × ...
```

Where:
- `tld_base` = base dollar value for the TLD (e.g., .com = $100)
- Each module's `value` field is read as a multiplier
- Missing modules (null) are omitted from the product (don't multiply by 1 or 0)

**Confidence range:**
```
range_low  = final_value × (1 - (1 - completeness_ratio) × 0.5)
range_high = final_value × (1 + (1 - completeness_ratio) × 0.5)
```

**Output format:**
```json
{
  "estimated_value": 4500,
  "range": { "low": 3200, "high": 5800 },
  "confidence": "medium",
  "completeness_ratio": 0.85,
  "missing_signals": ["M12 origin"],
  "breakdown": {
    "m2_tld": { "value": 8, "multiplier": 1 },
    "m4_word_count": { "score": 100, "multiplier": 20 },
    ...
  }
}
```

See `04-scoring-and-valuation.md` for worked examples.

---

## M16 — Brandability Scorer

**Purpose:** Only activates when M6 returns `no_split`. Assesses the domain as a brandable coinage — valuable as a startup/app/product name even though it has no dictionary meaning.

**Metrics:**

1. **Syllable flow** — 2–3 syllables ideal. Smooth consonant-vowel transitions score higher.
2. **Letter pattern scoring** — Certain endings feel brandable: -ify, -ly, -ex, -io, -o, -a, -r.
3. **Bigram/trigram frequency** — Common letter pairs are easier to remember and type.
4. **Cross-TLD availability** — If the .com brandable also has available .io/.net/.app variants, it's more valuable as a startup name.
5. **Phonetic uniqueness** — How distinct is the sound? "Google" is unique. "Blue" is common.

**Source:** Pure Python logic with pattern tables.

**Multiplier output:**
- High brandability (e.g., "nekowi", "vello") → ×5–×8
- Medium brandability (e.g., "yotop") → ×2–×4
- Low brandability (e.g., "fjfbfj") → ×1
- Not applicable (M6 found a split) → null

**Cache TTL:** Not cached (pure computation).
