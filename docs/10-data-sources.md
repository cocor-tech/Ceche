# Data Sources

Every external API and data source used by Ceche, with rate limits, attribution requirements, and fallback behavior.

---

## M1 — RDAP Lookup

| Field | Detail |
|---|---|
| **Endpoint** | `https://rdap.org/domain/{domain}` |
| **Type** | Free API, no key |
| **Rate limit** | None documented — be reasonable |
| **Signup required** | No |
| **Attribution** | None required |
| **Fallback** | None (core module) |
| **Cache TTL** | 24 hours |

---

## M2 — TLD Score Table

| Field | Detail |
|---|---|
| **Source** | Custom-built static JSON (`ceche/data/tld_scores.json`) |
| **Type** | Local data, embedded in codebase |
| **Rate limit** | None |
| **Signup required** | No |
| **Update frequency** | Manually as market changes (quarterly recommended) |

---

## M3, M4, M5, M13, M14, M16 — Local Computation

No external data sources. All are pure Python logic with embedded reference data:
- M3: sigmoid curve function
- M4: exponential curve function
- M5: bigram frequency table (embedded)
- M13: aggregation logic
- M14: SQLite (local file)
- M16: brandability pattern tables (embedded)

---

## M6 — Segmenter

| Field | Detail |
|---|---|
| **Library** | `wordfreq` Python package |
| **Word list** | google-10000-english |
| **Type** | Installed Python package |
| **Rate limit** | None |
| **Signup required** | No |

---

## M7 — Keyword Popularity

### Primary: pytrends

| Field | Detail |
|---|---|
| **Source** | `pytrends` Python library (unofficial Google Trends wrapper) |
| **Type** | Unofficial, scrape-based |
| **Rate limit** | Unofficial — expect occasional blocks |
| **Signup required** | No (Google account recommended) |
| **Caution** | Frequently breaks when Google updates their API. Caching is mandatory. |
| **Cache TTL** | 7 days |

### Fallback: Static keyword frequency map

| Field | Detail |
|---|---|
| **Source** | wordfreq + Google Books Ngram data |
| **Type** | Embedded data |
| **Rate limit** | None |
| **Size** | ~10,000 words with frequency scores |

---

## M8 — CPC / Commercial Intent

| Field | Detail |
|---|---|
| **Source** | Custom-built static JSON (~5,000 high-CPC keywords) |
| **Type** | Embedded data |
| **Rate limit** | None |
| **Signup required** | No |
| **Attribution** | Source data compiled from publicly available high-CPC keyword lists |
| **Cache TTL** | 30 days |

---

## M9 — Search Results

### Primary: Google Programmable Search Engine

| Field | Detail |
|---|---|
| **Endpoint** | Google Custom Search JSON API |
| **Type** | Free tier |
| **Rate limit** | 100 queries/day |
| **Signup required** | Yes — Google account + API key |
| **Setup** | 1. Create search engine at `programmablesearchengine.google.com`
2. Generate API key at `developers.google.com/custom-search/v1/introduction` |
| **Cache TTL** | 7 days |

### Backup: Brave Search API

| Field | Detail |
|---|---|
| **Endpoint** | Brave Search API |
| **Type** | Free tier |
| **Rate limit** | ~1,000 free queries/month |
| **Signup required** | Yes — `brave.com/search/api/` |
| **Cache TTL** | 7 days |

**Fallback chain:** Google CSE → Brave → No result (skip module)

---

## M10 — Cross-TLD Check

Reuses M1 (RDAP) for other TLDs + HTTP HEAD for parked detection. Same rate limits as M1.

---

## M11 — Trademark Check

### USPTO TSDR (US Trademarks)

| Field | Detail |
|---|---|
| **Endpoint** | `https://tsdr.uspto.gov/` |
| **Type** | Free, no key (web scrape) |
| **Rate limit** | None documented |
| **Signup required** | No |
| **Cache TTL** | 30 days |

### EUIPO eSearch (EU Trademarks)

| Field | Detail |
|---|---|
| **Endpoint** | `https://euipo.europa.eu/eSearch/` |
| **Type** | Free, no key (web scrape) |
| **Rate limit** | None documented |
| **Signup required** | No |
| **Cache TTL** | 30 days |

### WIPO Global Brand Database

| Field | Detail |
|---|---|
| **Endpoint** | `https://www3.wipo.int/branddb/en/` |
| **Type** | Free, manual search only (no official API) |
| **Rate limit** | N/A — for future enhancement |
| **Cache TTL** | 30 days |

---

## M12 — Backlink / History / Age

### Wayback Machine CDX API

| Field | Detail |
|---|---|
| **Endpoint** | `https://archive.org/wayback/available?url={domain}` |
| **Type** | Free API, no key |
| **Rate limit** | None documented — be reasonable |
| **Signup required** | No |
| **Attribution** | Not required but appreciated |
| **Output** | Snapshot count, earliest date, latest date |
| **Cache TTL** | 30 days |

### Ahrefs Domain Rating (Free)

| Field | Detail |
|---|---|
| **Endpoint** | `GET https://api.ahrefs.com/v3/public/domain-rating-free?target={domain}` |
| **Type** | Free public API, no key |
| **Rate limit** | Undocumented — enforced server-side via Cloudflare |
| **Signup required** | No |
| **Attribution** | Required: "Domain Rating by Ahrefs" (`ahrefs.com`) |
| **Output** | `domain_rating` (0–100), `license` URL |
| **Cache TTL** | 7 days |

### OpenPageRank

| Field | Detail |
|---|---|
| **Endpoint** | `POST https://openpagerank.keywordseverywhere.com/v1/domains/bulk` |
| **Type** | Free tier |
| **Rate limit** | 60 requests/min, 30,000 domains/month (free) |
| **Signup required** | Yes — Keywords Everywhere account (free) |
| **Attribution** | Not required |
| **Output** | `open_page_rank` (0–10), `rank`, `referring_domains`, `history` |
| **Cache TTL** | 7 days |

**Fallback chain:** Ahrefs + OPR both available → blended score. One available → score from available source, penalized. Neither → null.

---

## M14 — SQLite Cache

Local file, no external source. See `05-caching-layer.md`.

---

## Rate Limit Budget (Worst-Case Single Appraisal)

| Module | Calls per appraisal | Quota cost |
|---|---|---|
| M1 RDAP | 1 | ~1/∞ |
| M1 (M10 cross-TLD) | 5–10 | ~5–10/∞ |
| M7 pytrends | Up to word count (1–3) | 1–3 queries |
| M9 Google CSE | 1 | 1/100 daily |
| M9 Brave (backup) | 1 | 1/~1000 monthly |
| M11 USPTO | Up to word count | — (scrape) |
| M12 Wayback | 1 | ~1/∞ |
| M12 Ahrefs | 1 | 1/∞ |
| M12 OPR | 1 | 1/30,000 monthly |

With caching, repeated terms (e.g., "insurance" across 100 domains) only incur API cost once.
