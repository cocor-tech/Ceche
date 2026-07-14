# Layer 2 — Tool Registry

## Overview

The tool registry exposes every module's internal functions as typed, callable tools that the AI agent can invoke during reasoning. This gives the agent direct access to the same raw data and computation that the deterministic modules use — enabling it to cross-check, refine, and override results with full context.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Tool Registry                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   ToolDefinition                           │  │
│  │  name: str                                                │  │
│  │  description: str         # what the tool does             │  │
│  │  parameters: dict[str, ToolParam]  # typed input schema   │  │
│  │  returns: ToolReturn       # typed output schema          │  │
│  │  fn: Callable              # the actual function           │  │
│  │  module: str               # which module owns it          │  │
│  │  cost: float               # estimated token cost          │  │
│  │  cacheable: bool            # can results be cached        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   Registry Methods                         │  │
│  │  register(tool: ToolDefinition)                            │  │
│  │  get(name: str) -> ToolDefinition                          │  │
│  │  list_for_module(module: str) -> list[ToolDefinition]      │  │
│  │  generate_openai_schema() -> list[dict]                    │  │
│  │  execute(name: str, params: dict) -> Any                   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   Tool Execution                           │  │
│  │  validate(params) → sanitize → execute → validate(result)  │  │
│  │  errors → ToolExecutionError with typed failure detail     │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Tool Catalog (16 Tools Across 8 Modules)

### M1 — RDAP / Registration

| Tool | Signature | Description |
|---|---|---|
| `domain_registered` | `domain: str → bool` | Is this domain currently registered? |
| `domain_age` | `domain: str → float \| None` | Creation age in years |
| `domain_expiry` | `domain: str → date \| None` | Expiration date |

### M2 — TLD Score

| Tool | Signature | Description |
|---|---|---|
| `tld_score` | `tld: str → float` | Score 0.2–10 for any TLD |
| `tld_tier` | `tld: str → str` | Weight profile name (tier_10, etc.) |

### M5 — Pronounceability

| Tool | Signature | Description |
|---|---|---|
| `vowel_ratio` | `sld: str → float` | Vowel density 0.0–1.0 |
| `max_consonant_cluster` | `sld: str → int` | Longest run of consecutive consonants |
| `bigram_frequency` | `sld: str → float` | Average bigram frequency score |

### M6 — Segmenter

| Tool | Signature | Description |
|---|---|---|
| `word_break` | `sld: str → list[str] \| None` | DP word-break result |
| `word_frequency` | `word: str → float` | wordfreq frequency for any word |
| `valid_word` | `word: str → bool` | Passes the 1e-5 frequency threshold? |

### M7 — Keyword Popularity

| Tool | Signature | Description |
|---|---|---|
| `keyword_popularity` | `term: str → float` | 0–100 popularity score (pytrends or static) |

### M8 — CPC / Commercial Intent

| Tool | Signature | Description |
|---|---|---|
| `cpc_lookup` | `word: str → str \| None` | CPC tier from embedded map |
| `cpc_tier_rank` | `tier: str → int` | Numeric rank of tier (0=elite, 5=none) |

### M10 — Cross-TLD

| Tool | Signature | Description |
|---|---|---|
| `tld_exists` | `sld: str, tld: str → bool` | Does this SLD+TLD combination exist? |

### M11 — Trademark

| Tool | Signature | Description |
|---|---|---|
| `trademark_check` | `term: str → TrademarkResult` | USPTO known-marks check |
| `known_trademark` | `term: str → bool` | Is this in the curated marks list? |

### M12 — Authority

| Tool | Signature | Description |
|---|---|---|
| `wayback_snapshots` | `domain: str → int` | Snapshot count from CDX API |
| `ahrefs_dr` | `domain: str → float \| None` | Domain Rating 0–100 |
| `opr_score` | `domain: str → float \| None` | OpenPageRank 0–10 |

## Tool Parameters — Typed Schema

```python
@dataclass
class ToolParam:
    name: str
    type: str              # "str" | "int" | "float" | "bool"
    required: bool
    description: str
    enum: list[str] | None = None   # allowed values if constrained

@dataclass
class ToolReturn:
    type: str              # "str" | "int" | "float" | "bool" | "list" | "dict" | "null"
    description: str
    nullable: bool = False
```

## OpenAI Function Calling Schema

The registry auto-generates OpenAI-compatible function definitions:

```python
{
    "name": "word_break",
    "description": "Break a domain SLD into valid English words using dynamic programming",
    "parameters": {
        "type": "object",
        "properties": {
            "sld": {
                "type": "string",
                "description": "The second-level domain string to break into words"
            }
        },
        "required": ["sld"]
    }
}
```

The AI agent passes this schema to OpenAI/Claude so it can call tools natively.

## Execution Sandbox

Every tool call goes through a validation layer:

```python
async def execute(self, name: str, params: dict) -> ToolResult:
    tool = self.get(name)
    # 1. Validate all required params present
    # 2. Type-check each param against ToolParam.type
    # 3. Sanitize strings (strip, lowercase, no injection)
    # 4. Execute the function
    # 5. Validate return type matches ToolReturn.type
    # 6. Log execution (tool name, params, result, latency)
    # 7. Return ToolResult(value, latency_ms)
```

## Tool Composition

The agent can chain tools. Example reasoning chain for "gojominitia.com":

```
1. Call word_break("gojominitia") → ["go","jo","min","it","i","a"]
2. Call word_frequency("go") → 0.00617
3. Call word_frequency("jo") → (check) → 0.00000823
4. Agent reasons: "jo" has very low frequency. 6-word split suspicious.
5. Agent produces: SINGLE (brandable) — no valid segmentation
6. Result: M6 returns no_split → M16 brandability takes over
```

## Caching

Tools with `cacheable=True` use the M14 SQLite cache layer. Key format: `ai_tool:{tool_name}:{param_hash}`. TTL: 24 hours for static data tools, 7 days for frequency/authority tools, session-only for registration tools.

## Implementation Files

```
ceche/infrastructure/ai/
├── tools/
│   ├── __init__.py
│   ├── registry.py       # ToolRegistry — register, get, execute, schema gen
│   ├── definition.py     # ToolDefinition, ToolParam, ToolReturn dataclasses
│   ├── sandbox.py        # Execution sandbox — validate, sanitize, execute
│   └── catalog.py        # All 16 tool registrations (imports from each module)
```

## Dependencies

- None beyond existing Python stdlib + domain module imports
- OpenAI function schema generation is handled internally (no external dep)

## Best Practices

### Tool Design
- Each tool should have a single, focused responsibility. If a tool does two things (e.g., "check registration AND get age"), split it into two tools.
- Tool names must use snake_case and be self-documenting: `domain_registered`, not `chkreg` or `check_domain_registration_status`.
- Every tool description must include what it RETURNS, not just what it does. "Returns True if the domain is currently registered, False otherwise" is better than "Checks domain registration."
- Set `cacheable=True` for any tool whose result doesn't change within a single appraisal session. This prevents the AI from calling the same tool twice.

### Parameter Validation
- Never trust AI-generated parameters. Validate every field before execution — type check (str vs int vs float), range check (scores must be 0-100), and allowlist check (tld must be in IANA list).
- Reject parameters that contain shell metacharacters, SQL injection patterns, or path traversal sequences (`../`, `/etc/`).
- Return descriptive validation errors: `{"error": "param 'score' must be 0-100, got 150"}` not `{"error": "invalid"}`.

### Execution Sandbox
- All tool execution runs in a separate asyncio task with a 5-second timeout. Tools that don't complete within 5 seconds are killed and return a timeout error.
- Tools must be pure functions — no filesystem access, no network calls unless explicitly part of their contract (like `ahrefs_dr` which makes an HTTP call).
- After execution, validate that the return value matches the declared `ToolReturn` type before passing it back to the AI.

## Common Mistakes & How to Avoid Them

| Mistake | Why It Happens | Prevention |
|---|---|---|
| **Tool returns None silently** | Function returns None when data is missing, no error raised | Wrap every tool in `_safe_execute()` that converts None to a typed error response |
| **AI calls same tool repeatedly** | Agent gets stuck in a reasoning loop | Implement per-call deduplication: if same tool+params called within single reasoning chain, return cached result |
| **Sensitive data leaked to AI** | Tool returns raw API responses with API keys embedded | Strip `Authorization` headers and any key-like fields from tool results before returning to AI |
| **Tool modifies global state** | Tool has side effects (writes to DB, modifies context dict) | Mark tools as read-only by default. Write tools must be explicitly annotated and logged. |
| **Tool description doesn't match behavior** | Code changed but description wasn't updated | Add integration test that: calls tool → checks return type matches ToolReturn declaration |
| **AI calls wrong tool with right intent** | Tool names are too similar (`get_score` vs `get_scores`) | Name tools distinctly. Use the module prefix: `m6_word_break`, `m12_ahrefs_dr` |

## Enterprise-Grade Implementation Checklist

- [ ] Every tool has a `ToolDefinition` with typed params and return type
- [ ] Param validation rejects: shell metacharacters, SQL injection, path traversal
- [ ] 5-second execution timeout per tool call
- [ ] Deduplication: same tool+params not called twice in one reasoning chain
- [ ] Sensitive data stripped from tool results before returning to AI
- [ ] Integration test: every tool returns correct ToolReturn type
- [ ] Integration test: None return value triggers error, not silent failure
- [ ] Integration test: invalid params rejected with descriptive error
- [ ] Tools annotated as read-only by default; write tools explicitly marked
- [ ] Tool descriptions include return type in plain English
- [ ] All 16 tools have at least one unit test
