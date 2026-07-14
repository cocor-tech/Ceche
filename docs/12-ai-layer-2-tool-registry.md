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
