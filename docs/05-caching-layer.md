# Caching Layer (M14)

## Purpose

Cache lookups by term/segment, not by full domain. Common words like "top", "shop", "get", "insurance" repeat across thousands of domain queries. Caching them prevents burning free-tier API quotas on duplicate lookups.

## Storage

**SQLite** — built into Python, zero setup, zero hosting cost, single file, persistent between runs.

**Database file:** `ceche/cache/cache.db`

## Schema

```sql
CREATE TABLE cache (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,          -- JSON blob of the cached result
    ttl         INTEGER NOT NULL,       -- in seconds
    created_at  INTEGER NOT NULL,       -- Unix timestamp
    expires_at  INTEGER NOT NULL        -- created_at + ttl
);

CREATE INDEX idx_expires ON cache(expires_at);
```

## Key Format

```
{module_name}:{query_term}
```

Examples:

| Module | Cache Key | Value Example |
|---|---|---|
| M1 RDAP | `rdap:example.com` | `{"registered": true, "creation_date": "1997-01-01", ...}` |
| M7 Keyword | `pytrends:insurance` | `{"score": 85, "data": ...}` |
| M7 Fallback | `kw_static:insurance` | `{"score": 78, "tier": "high"}` |
| M8 CPC | `cpc:insurance` | `{"tier": "elite", "cpc_range": "50-100"}` |
| M9 Search | `search:topinsurance.com` | `{"result_count": 1500, ...}` |
| M9 Brave | `brave:topinsurance.com` | `{"result_count": 1200, ...}` |
| M12 Ahrefs | `ahrefs:example.com` | `{"dr": 45, "ref_domains": 1200}` |
| M12 Wayback | `wayback:example.com` | `{"snapshots": 500, "first": "2005-01-01"}` |
| M12 OPR | `opr:example.com` | `{"score": 6.5, "rank": 50000}` |

## TTL Per Module

| Module / Source | TTL | Rationale |
|---|---|---|
| M1 RDAP | 24 hours | Registration status rarely changes day-to-day |
| M2 TLD scores | 90 days | Static data, update quarterly |
| M6 Segmentations | 30 days | Word lists are stable |
| M7 pytrends | 7 days | Trends shift week-to-week |
| M7 static map | 365 days | Never changes (embedded data) |
| M8 CPC map | 30 days | Static data |
| M9 Google CSE | 7 days | SERPs shift |
| M9 Brave | 7 days | |
| M11 USPTO | 30 days | New filings daily, but re-checking is fine |
| M11 EUIPO | 30 days | |
| M12 Ahrefs DR | 7 days | Authority changes slowly |
| M12 Wayback | 30 days | History accumulates slowly |
| M12 OPR | 7 days | Monthly crawl updates |

## Interface

```python
class M14Cache:
    def __init__(self, db_path: str = "ceche/cache/cache.db")

    def get(self, key: str) -> dict | None:
        """Retrieve cached value. Returns None if missing or expired."""

    def set(self, key: str, value: dict, ttl: int):
        """Store a cached value with TTL in seconds."""

    def get_or_compute(self, key: str, ttl: int, fn: Callable) -> dict:
        """Check cache → if miss, call fn() → store result → return.
        This is the primary interface modules use."""

    def cleanup(self):
        """Remove all expired entries. Run on startup and every 100 writes."""

    def clear(self):
        """Clear the entire cache (for testing or --no-cache mode)."""
```

## Module Integration

Every module that calls an external API wraps the call with `cache.get_or_compute()`:

```python
# Before (no cache):
result = await rdap_lookup("example.com")

# After (with cache):
result = await cache.get_or_compute(
    key=f"rdap:example.com",
    ttl=86400,  # 24 hours
    fn=lambda: rdap_lookup("example.com")
)
```

This keeps module code clean — they just pass a key, TTL, and the actual fetch function.

## CLI Integration

```
ceche appraise example.com         # uses cache normally
ceche appraise example.com --fresh # bypass cache for all lookups
```

The `--fresh` flag sets a session-level bypass. Existing cached data is not deleted, but all gets go through to the API.

## Cache Stats

After each appraisal run, the output includes:

```json
{
  "cache_hits": 4,
  "cache_misses": 2,
  "cache_hit_rate": 0.67
}
```

## Auto-Cleanup

- `cleanup()` runs automatically on module init
- Also runs every 100 writes (checkpoint)
- Purges all rows where `expires_at < now()`

## Size Considerations

Each cached entry is a small JSON blob (100–2000 bytes). Even with 100,000 cached terms, the database stays under 200MB. SQLite handles this easily without any noticeable performance impact.

## Upgrading Later

When call volume justifies it, SQLite can be replaced with:
- **Redis** — for multi-process/network access, built-in TTL expiry, better performance at scale
- Migration path: keep the same `get()`/`set()`/`get_or_compute()` interface, swap the backend
