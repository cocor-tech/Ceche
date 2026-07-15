# Ceche Bulk Valuation — Enterprise Upgrade Plan

## Overview

Enable concurrent domain valuation at 10-way parallelism with rate-limited external API calls, full failure isolation, Rich progress tracking, and raw JSON output. The existing `AppraisalEngine` stays untouched except for a `fresh` bypass parameter — all concurrency lives in a new `BulkAppraisalEngine` wrapper.

## Architecture

```
                        ┌──────────────────────────┐
   domains.txt ──►      │   BulkAppraisalEngine     │
   CLI args ────►       │                           │
   stdin pipe ──►       │   Semaphore(10)           │
                        │   ┌───────────────────┐   │
                        │   │  AppraisalEngine   │   │
                        │   │   appraise(d) #1   │──► result
                        │   │   appraise(d) #2   │──► result
                        │   │   ...              │   │
                        │   │   appraise(d) #10  │──► or BulkFailure
                        │   └───────────────────┘   │
                        │   RateLimiter (per prov)  │
                        │   Rich Progress Bar       │
                        └──────────────────────────┘
                                    │
                                    ▼
                          {summary, results[], failures[]}
```

### Rate Limiting

Injected at the `httpx.AsyncClient` transport layer. Each adapter already accepts `client=httpx.AsyncClient(...)` — we pass rate-limited clients. **Zero changes to adapter internals.**

```
Provider     Rate (req/s)   Burst   Rationale
────────────────────────────────────────────────────
rdap          5              10     rdap.org has no published limit
deepseek      5              15     Higher burst for bulk AI calls
kimi          3              10     Conservative
glm           3              10     Conservative
minimax       3              10     Conservative
openai        5              15     Standard rate
google_cse   10              20     Standard quota 100 req/100s
wayback       5              10     archive.org is lenient
ahrefs        1               3     Free tier
opr           2               5     Free tier
brave         5              10     Conservative
```

### Token Bucket Algorithm

- Tokens refill at `rate` tokens/second, capped at `burst`
- On `acquire()`: refill based on elapsed time, if tokens < 1, sleep until 1 token available
- Uses `asyncio.Lock` for concurrent safety
- Non-blocking `acquire_nowait()` returns bool immediately

---

## Implementation Milestones

### M1: Rate Limiter Infrastructure

**Files:**
- `ceche/infrastructure/rate/__init__.py` — package init, exports
- `ceche/infrastructure/rate/bucket.py` — `TokenBucket` async class

`TokenBucket`:
- `__init__(rate: float, burst: int = 10)`
- `async acquire() -> None` — blocks until token available
- `acquire_nowait() -> bool` — non-blocking check

- `ceche/infrastructure/rate/limiter.py` — `RateLimiter` + `RateLimitedTransport`

`RateLimiter`:
- `__init__()` — creates buckets for each known provider from config dict
- `async acquire(provider: str) -> None` — acquires from that provider's bucket
- Uses `_BURST_CONFIG` and `_RATE_CONFIG` dicts for defaults

`RateLimitedTransport`:
- Wraps `httpx.AsyncBaseTransport`
- `async handle_async_request(request)` — calls `limiter.acquire(provider)` then delegates
- Allows `httpx.AsyncClient(transport=RateLimitedTransport(...))` pattern

**Tests:** `tests/test_rate_limiter.py` — TokenBucket refill logic, concurrency, burst behavior

---

### M2: Engine Fresh Parameter

**Files:**
- `ceche/engine.py` — `appraise()` signature extended with `fresh: bool = False`
- `ceche/domain/modules/m01_rdap.py` — skip cache when `context["_fresh"]` is set

Changes in engine:
```python
async def appraise(self, domain: str, fresh: bool = False) -> AppraisalResult:
    ctx["_fresh"] = fresh  # passed through to M1
```

Changes in M1 `run()`:
```python
if context.get("_fresh"):
    raw = await self._rdap.lookup(domain)
else:
    raw = await self._cache.get_or_compute(...)
```

**Tests:** Existing engine tests still pass; new test verifies cache bypass

---

### M3: AI Router Rate Limiting

**File:**
- `ceche/infrastructure/ai/router.py` — accept `RateLimiter`, call before each `complete()`

```python
class ModelRouter:
    def __init__(self, rate_limiter: RateLimiter | None = None):
        self._limiter = rate_limiter

    async def complete(self, module: str, prompt: str, system: str = "") -> str:
        spec = self.get_spec(module)
        if self._limiter:
            await self._limiter.acquire(spec.provider)
        ...
```

**Tests:** Existing AI tests still pass; integration verified in M5

---

### M4: BulkAppraisalEngine

**File:**
- `ceche/bulk_engine.py` — `BulkAppraisalEngine` + report dataclasses

Dataclasses:

```python
@dataclass
class BulkFailure:
    domain: str
    error_type: str          # e.g. "ExternalServiceError", "TimeoutException"
    error_message: str       # Full message, never truncated
    phase: str | None        # Module name like "m1_rdap" or None
    traceback: str | None    # Only for unexpected exceptions

@dataclass
class BulkSummary:
    total: int
    succeeded: int
    failed: int
    duration_seconds: float
    rate_domains_per_second: float

@dataclass
class BulkReport:
    summary: BulkSummary
    results: list[AppraisalResult]
    failures: list[BulkFailure]
```

Engine:

```python
class BulkAppraisalEngine:
    def __init__(self, engine: AppraisalEngine, concurrency: int = 10, fresh: bool = False):
        self._engine = engine
        self._sem = asyncio.Semaphore(concurrency)
        self._fresh = fresh

    async def run(
        self,
        domains: list[str],
        on_progress: Callable[[int, int, int], None] | None = None,
    ) -> BulkReport:
```

Implementation details:
- Wrap each domain in `_appraise_one()` with semaphore gate
- Each domain gets its own try/except — failures are captured, not propagated
- Use `asyncio.as_completed()` for streaming completion (results output as they finish)
- Track start time, completed count, failed count
- `on_progress(total, succeeded, failed)` callback after each domain
- Phase detection for failures: parse exception message for module name, or use exception type

**Tests:** `tests/test_bulk_engine.py` — concurrent processing, failure isolation, report structure, semaphore enforcement

---

### M5: CLI `bulk` Command

**File:**
- `ceche/interfaces/cli/__init__.py` — new `bulk` command + refactored builder
- `ceche/config.py` — add `concurrency: int = 10`

Command:

```bash
ceche bulk [DOMAINS...] [OPTIONS]

Options:
  -c, --concurrency INTEGER   Max concurrent domains (1-100, default: 10)
  -f, --fresh                 Force recheck — bypass all caches

Input:
  ceche bulk domain1.com domain2.com        # CLI args
  ceche bulk domains.txt                     # File (auto-detected)
  cat domains.txt | ceche bulk               # stdin pipe
  cat domains.txt | ceche bulk extra.com     # stdin + args combined
```

`_resolve_domains()` updated:
```python
def _resolve_domains(args: list[str]) -> list[str]:
    # 1. Read from stdin if pipe
    # 2. If single arg is a file, read it
    # 3. Otherwise use args directly
    # 4. Combine all sources, deduplicate
```

`_build_engine()` refactored to accept rate limiter:
```python
def _build_engine(cfg: Config, rate_limiter: RateLimiter | None = None) -> AppraisalEngine:
    # Create per-provider rate-limited httpx clients via RateLimitedTransport
    # Pass rate_limiter to router
```

Progress bar via `rich.progress.Progress` (on stderr):
```
⏳ Appraising 100 domains (10 concurrent)...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 73/100 · 5 failed · 2.4/s · ETA 11s
```

Output (stdout, always full JSON):
```json
{
  "summary": {
    "total": 100,
    "succeeded": 95,
    "failed": 5,
    "duration_seconds": 42.3,
    "rate_domains_per_second": 2.36
  },
  "results": [
    {
      "domain": "namesranker.com",
      "estimated_value": 8331.0,
      "range": {"low": 6000.0, "high": 11000.0},
      "confidence": "medium",
      "completeness_ratio": 0.87,
      "tld_score": 10.0,
      "weight_profile": "tier_08",
      "modules": {
        "m1_rdap": {"registered": true, "age_years": 8.3, "status": "success"},
        "m2_tld_table": {"tld_score": 10, "weight_profile": "tier_08", "status": "success"},
        "...all 14 modules..."
      }
    }
  ],
  "failures": [
    {
      "domain": "timeout-domain.xyz",
      "error_type": "ExternalServiceError",
      "error_message": "timeout querying timeout-domain.xyz: Read timed out",
      "phase": "m1_rdap",
      "traceback": null
    }
  ]
}
```

Exit codes:
- `0` — at least one domain succeeded
- `1` — all domains failed or no valid domains provided

---

### M6: Tests, Lint, Push, End-to-End Verification

**Files:**
- `tests/test_rate_limiter.py` — TokenBucket correctness, burst overflow, concurrent acquire, rate enforcement
- `tests/test_bulk_engine.py` — 1 domain, 10 domains, 50 domains, failure isolation, report structure, semaphore enforcement, empty domain list

**Verification:**
```bash
ruff check . && mypy ceche/ --ignore-missing-imports && pytest tests/ -q
echo "example.com\ntest.com\nnamesranker.com\ngoogle.com" > /tmp/bulk_test.txt
ceche bulk /tmp/bulk_test.txt --fresh 2>&1 | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{d[\"summary\"]}')"
```

---

## Summary

| Milestone | Files Created | Files Modified | Estimated Lines |
|---|---|---|---|
| M1: Rate Limiter | 3 | 0 | ~120 |
| M2: Engine Fresh | 0 | 2 | ~10 |
| M3: AI Router | 0 | 1 | ~10 |
| M4: Bulk Engine | 1 | 0 | ~120 |
| M5: CLI Command | 0 | 2 | ~180 |
| M6: Tests + Verify | 2 | 0 | ~100 |
| **Total** | **6** | **5** | **~540** |
