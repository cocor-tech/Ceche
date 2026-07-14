# Layer 6 — Observability & Control

## Overview

Production-grade monitoring for all AI interactions. Structured audit logging, circuit breaker for provider failures, cost tracking with daily budgets, latency monitoring, and a health endpoint for external monitoring systems.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                       Observability System                           │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
│  │ AuditLogger  │  │ CostTracker  │  │ CircuitBreaker             │  │
│  │ (structured  │  │ (per-domain, │  │ (error rate, state,        │  │
│  │  JSON logs)  │  │  daily caps) │  │  auto-recovery)            │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────────┘  │
│         │                 │                        │                 │
│  ┌──────┴─────────────────┴────────────────────────┴──────────────┐  │
│  │                     Health Endpoint                              │  │
│  │  GET /v1/ai/health                                               │  │
│  │  → {provider, status, error_rate, cost_today, uptime, latency}   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    OpenTelemetry Integration                      │  │
│  │  spans for: ai_call, tool_execution, prompt_render, response_parse│  │
│  │  traces link: domain → module → prompt → tool → result            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

## Audit Logger

### Schema (SQLite)

```sql
CREATE TABLE IF NOT EXISTS ai_audit (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     INTEGER NOT NULL,       -- Unix ms
    domain        TEXT NOT NULL,          -- domain being appraised
    module        TEXT NOT NULL,          -- which module used AI
    prompt_id     TEXT NOT NULL,          -- which prompt was used
    prompt_version TEXT NOT NULL,         -- prompt version
    provider      TEXT NOT NULL,          -- "openai" | "anthropic" | "ollama"
    model         TEXT NOT NULL,          -- "gpt-4o-mini" etc.
    prompt_text   TEXT NOT NULL,          -- full prompt sent
    response_text TEXT NOT NULL,          -- full response received
    tools_called  TEXT NOT NULL,          -- JSON array of tool names
    tool_results  TEXT NOT NULL,          -- JSON object of tool results
    latency_ms    INTEGER NOT NULL,       -- total call duration
    tokens_in     INTEGER NOT NULL,       -- prompt tokens
    tokens_out    INTEGER NOT NULL,       -- completion tokens
    cost_usd      REAL NOT NULL,          -- actual cost in USD
    success       INTEGER NOT NULL,       -- 0 or 1
    error_detail  TEXT,                   -- error message if failed
    original_value TEXT,                  -- JSON: original module result
    blended_value TEXT,                   -- JSON: blended result
    blending_weight REAL                  -- 0.0–1.0
);

CREATE INDEX IF NOT EXISTS idx_ai_audit_time ON ai_audit(timestamp);
CREATE INDEX IF NOT EXISTS idx_ai_audit_module ON ai_audit(module);
CREATE INDEX IF NOT EXISTS idx_ai_audit_domain ON ai_audit(domain);
```

### Log Format

```json
{
  "timestamp": "2026-07-14T12:00:05.123Z",
  "domain": "gojominitia.com",
  "module": "m6",
  "prompt_id": "m06_segmenter_disambiguate",
  "prompt_version": "1.0.0",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "tools_called": ["word_break", "word_frequency", "valid_word"],
  "latency_ms": 847,
  "tokens_in": 312,
  "tokens_out": 12,
  "cost_usd": 0.000312,
  "success": true,
  "original_value": {"winner": ["go","jo","min","it","i","a"], "word_count": 6},
  "blended_value": {"winner": null, "word_count": null, "status": "no_split"},
  "blending_weight": 1.0
}
```

## Circuit Breaker

Protects against provider outages and cascading failures.

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self._failure_threshold = failure_threshold    # consecutive failures
        self._recovery_timeout = recovery_timeout        # seconds before retry
        self._failure_count = 0
        self._last_failure_time = 0
        self._state = "closed"   # closed | open | half_open

    @property
    def is_open(self) -> bool:
        if self._state == "open":
            if time.time() - self._last_failure_time > self._recovery_timeout:
                self._state = "half_open"
                return False
            return True
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = int(time.time())
        if self._failure_count >= self._failure_threshold:
            self._state = "open"

    def status(self) -> dict:
        return {
            "state": self._state,
            "failure_count": self._failure_count,
            "last_failure": self._last_failure_time,
            "threshold": self._failure_threshold,
            "recovery_in": max(0, self._recovery_timeout - (time.time() - self._last_failure_time))
            if self._state == "open" else 0,
        }
```

**State machine:**

```
CLOSED ──(5 consecutive failures)──▶ OPEN
  ▲                                    │
  │                                    │ (5 min timeout)
  │                                    ▼
  └────────(success)────────── HALF_OPEN ──(failure)──▶ OPEN
```

When OPEN: all AI calls are skipped, deterministic-only mode with WARNING log.

## Cost Tracker

```python
class CostTracker:
    def __init__(self, daily_budget: float = 1.00, per_domain_budget: float = 0.01):
        self._daily_budget = daily_budget
        self._per_domain = per_domain_budget
        self._daily_spend = 0.0
        self._domain_spend: dict[str, float] = {}
        self._reset_at_midnight()

    def can_spend(self, domain: str, estimated: float) -> bool:
        if self._daily_spend + estimated > self._daily_budget:
            return False
        current = self._domain_spend.get(domain, 0.0)
        if current + estimated > self._per_domain:
            return False
        return True

    def track(self, domain: str, actual: float) -> None:
        self._daily_spend += actual
        self._domain_spend[domain] = self._domain_spend.get(domain, 0.0) + actual

    def summary(self) -> dict:
        return {
            "daily_spend": round(self._daily_spend, 4),
            "daily_budget": self._daily_budget,
            "daily_remaining": round(self._daily_budget - self._daily_spend, 4),
            "per_domain_budget": self._per_domain,
            "domains_appraised": len(self._domain_spend),
            "avg_cost_per_domain": round(self._daily_spend / max(1, len(self._domain_spend)), 4),
        }
```

### Cost Estimates (GPT-4o-mini)

| Module | Tokens In | Tokens Out | Cost |
|---|---|---|---|
| M5 (pronounce) | ~150 | ~15 | $0.00005 |
| M6 (disambiguate) | ~300 | ~15 | $0.00010 |
| M7 (keyword) | ~150 | ~15 | $0.00005 |
| M8 (CPC) | ~150 | ~15 | $0.00005 |
| M11 (trademark) | ~150 | ~15 | $0.00005 |
| M13 (confidence) | ~200 | ~20 | $0.00007 |
| M15 (pricing) | ~250 | ~25 | $0.00009 |
| M16 (brandability) | ~200 | ~25 | $0.00007 |
| **Total per domain** | ~1,550 | ~145 | **~$0.00053** |

At $0.00053 per appraisal, 1,000 domains/month costs $0.53. The daily budget of $1.00 allows ~1,887 appraisals/day.

## Latency Monitoring

Every AI call records latency. Aggregated per module:

```json
{
  "m6_segmenter": {
    "count": 45,
    "avg_ms": 847,
    "p50_ms": 720,
    "p95_ms": 1200,
    "p99_ms": 1800,
    "max_ms": 3200
  }
}
```

Slow modules (avg > 2s) trigger WARNING log. Timeout set at 10s per call.

## Health Endpoint

```
GET /v1/ai/health
```

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "status": "healthy",
  "circuit_breaker": {
    "state": "closed",
    "failure_count": 0
  },
  "cost": {
    "daily_spend": 0.0032,
    "daily_budget": 1.00,
    "daily_remaining": 0.9968,
    "per_domain_budget": 0.01
  },
  "latency": {
    "avg_ms": 847,
    "p95_ms": 1200,
    "max_ms": 3200
  },
  "uptime_seconds": 86400,
  "total_calls": 45,
  "success_rate": 0.978
}
```

## OpenTelemetry Integration

```python
from opentelemetry import trace
tracer = trace.get_tracer("ceche.ai")

async def ai_call_with_tracing(module: str, prompt: str, tools: list):
    with tracer.start_as_current_span(f"ai.{module}") as span:
        span.set_attribute("module", module)
        span.set_attribute("prompt_id", prompt.id)
        span.set_attribute("tools_called", ",".join(t.name for t in tools))

        start = time.monotonic()
        try:
            result = await adapter.complete(prompt, tools)
            span.set_attribute("success", True)
            span.set_attribute("latency_ms", (time.monotonic() - start) * 1000)
            return result
        except Exception as e:
            span.set_attribute("success", False)
            span.record_exception(e)
            raise
```

Traces link through the full appraisal: `appraise → m6_ai → word_break → response → blend → result`.

## Alerts

| Condition | Level | Action |
|---|---|---|
| Circuit breaker OPEN | CRITICAL | Log, switch to deterministic-only |
| Daily budget 90% consumed | WARNING | Log, throttle low-priority modules |
| Daily budget exhausted | ERROR | Log, disable AI for remaining day |
| Latency P95 > 5s | WARNING | Log, consider model downgrade |
| Error rate > 20% (1 min window) | ERROR | Log, open circuit breaker |
| Single domain cost > $0.05 | WARNING | Log, flag for review |

## Implementation Files

```
ceche/infrastructure/ai/
├── monitoring/
│   ├── __init__.py
│   ├── audit.py           # AuditLogger — SQLite schema, log methods
│   ├── circuit.py         # CircuitBreaker — state machine
│   ├── cost_tracker.py    # CostTracker — daily/per-domain budgets
│   ├── latency.py         # LatencyMonitor — per-module aggregation
│   ├── health.py          # Health endpoint response builder
│   └── otel.py            # OpenTelemetry tracer setup
```

## Best Practices

### Audit Logging
- Log EVERY AI interaction, including failed calls and timeouts. A call that timed out tells you the provider is unhealthy — this is as valuable as a successful call.
- Include the first 200 characters of the prompt and response in the audit log. Truncate longer content. This gives enough context for debugging without blowing up storage.
- Use structured JSON for the `detail` fields, not free-text strings. Every log entry should be queryable by: domain, module, prompt_id, provider, success, cost_range.
- Ship audit logs off-instance within 60 seconds. If the app crashes, you still have the logs. Use a sidecar process or a background thread that tails the SQLite WAL file.

### Circuit Breaker Tuning
- Set the failure threshold based on your call volume. Low volume (≤10 calls/min): threshold=3 failures. High volume (>100 calls/min): threshold=10 failures. The goal is to trip within 1 minute of a provider outage.
- When the circuit opens, switch to the next available provider, not to NoOp. Only fall to NoOp if all providers are unhealthy.
- Log every state transition (CLOSED→OPEN, OPEN→HALF_OPEN, HALF_OPEN→CLOSED, HALF_OPEN→OPEN) at WARNING level. These are operations-critical events.
- In HALF_OPEN state, only allow 1 request through. If it succeeds, close the circuit. If it fails, reopen immediately. Don't flood a recovering provider.

### Cost Management
- Implement provider-specific cost calculation from the `usage` response object, not from hardcoded estimates. Different models have different pricing, and prices change.
- Track cost per module, not just total cost. This reveals which modules are the most expensive to run AI on — enabling targeted optimization.
- Set a soft cap at 80% of daily budget that triggers a `WARNING` log but doesn't stop processing. Set a hard cap at 100% that stops all AI calls for the day.
- Include cost in the appraisal result metadata so users can see how much AI cost to produce their valuation.

### Alerting
- CRITICAL alerts (circuit breaker open, all providers down) should go to PagerDuty/OpsGenie.
- WARNING alerts (budget 80% consumed, latency P95 > 5s) should go to Slack/Teams.
- INFO alerts (provider switched, daily cost summary) should go to a dashboard only.

## Common Mistakes & How to Avoid Them

| Mistake | Why It Happens | Prevention |
|---|---|---|
| **Circuit breaker never recovers** | Provider comes back but HALF_OPEN test request fails on a slow endpoint | Use a lightweight health check endpoint for HALF_OPEN tests, not a full prompt+response call |
| **Cost tracking misses async calls** | `cost_tracker.track()` called before the async call completes, not after | Track cost in the finally block: `try: result = await ai_call(); finally: cost_tracker.track(cost)` |
| **Audit table locks under concurrent writes** | SQLite single-writer limitation | Use WAL mode (PRAGMA journal_mode=WAL). If concurrent writes exceed 100/min, migrate to PostgreSQL. |
| **Alerts fire for expected behavior** | Circuit breaker opens because provider does weekly maintenance | Add a maintenance window config that suppresses alerts during known downtime |
| **Latency monitoring averages hide P99 problems** | Averaging smooths out spikes | Always report P50, P95, P99, and max. Never report average alone. |
| **Daily budget resets at wrong time** | Budget reset uses server local time instead of UTC | Always use UTC for budget resets. Store `reset_at_utc` in the tracker. |

## Enterprise-Grade Implementation Checklist

- [ ] Every AI interaction logged (success AND failure), shipped off-instance within 60 seconds
- [ ] First 200 chars of prompt/response included in audit, rest truncated
- [ ] Structured JSON detail fields, queryable by domain/module/prompt/provider/success
- [ ] Circuit breaker: threshold tuned to call volume, state transitions logged at WARNING
- [ ] Circuit breaker: HALF_OPEN uses lightweight health check, only 1 test request
- [ ] Circuit breaker: falls back to next provider before falling to NoOp
- [ ] Cost calculated from actual usage response, not hardcoded estimates
- [ ] Cost tracked per module AND per domain
- [ ] Soft cap (80% budget) logs WARNING; hard cap (100%) stops all AI
- [ ] Cost included in appraisal result metadata
- [ ] CRITICAL alerts → PagerDuty; WARNING → Slack; INFO → dashboard
- [ ] Maintenance window config to suppress expected downtime alerts
- [ ] SQLite WAL mode enabled; migration path to PostgreSQL documented
- [ ] P50/P95/P99/max latency reported; never average alone
- [ ] Budget resets use UTC exclusively
- [ ] Integration test: circuit breaker opens after N failures
- [ ] Integration test: cost hard cap stops AI calls
- [ ] Integration test: audit log survives process crash (WAL recovery)
