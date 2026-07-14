# Layer 4 — AI Agent Orchestrator

## Overview

The Agent Orchestrator coordinates all AI interactions across the appraisal pipeline. It does not replace any module — deterministic modules always run first. The orchestrator evaluates each module's output confidence, spawns reasoning chains when needed, calls tools from the registry, invokes prompts from the catalog, and blends AI-refined results with original results by confidence weight.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      AgentOrchestrator                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    Pipeline Hook                             │    │
│  │  1. Domain enters engine                                     │    │
│  │  2. All deterministic modules run                            │    │
│  │  3. Orchestrator evaluates each module's output              │    │
│  │  4. For modules needing refinement → spawns AI chain         │    │
│  │  5. AI chain: prompt → tool calls → reasoning → result       │    │
│  │  6. Blend: original × (1-w) + ai_result × w                  │    │
│  │  7. Updated result flows to downstream modules               │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                  Refinement Policy                            │    │
│  │  module: M6  trigger: word_count >= 4                        │    │
│  │  module: M6  trigger: status == "no_split"                   │    │
│  │  module: M7  trigger: domain_score < 10 AND pytrends_failed  │    │
│  │  module: M8  trigger: tier == "none"                         │    │
│  │  module: M11 trigger: severity == "none"                     │    │
│  │  module: M13 trigger: completeness < 0.8                     │    │
│  │  module: M15 trigger: value outside expected tier range      │    │
│  │  module: M16 trigger: always (brandable)                     │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                  Reasoning Engine                             │    │
│  │  agent.with_tools(registry.get_for_module(module))            │    │
│  │       .with_prompt(catalog.get(trigger))                      │    │
│  │       .on_step(callback=audit_log)                            │    │
│  │       .run() → AIResponse                                     │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Module runs deterministically
  │
  ▼
Orchestrator.evaluate(module_result)
  │
  ├── confidence >= 0.9 AND no trigger condition
  │      → pass through (no AI needed)
  │
  ├── confidence < threshold OR trigger condition matched
  │      → spawn AI chain:
  │
  │      1. Catalog.get_prompt(trigger_type)
  │      2. Registry.get_tools(module_name)
  │      3. Agent.run(prompt, tools, context)
  │         → Agent may call tools (word_break, cpc_lookup, etc.)
  │         → Agent reasons over tool results
  │         → Agent produces structured response
  │      4. Parser.parse(response)
  │      5. ResultBlender.blend(original, ai_result)
  │         blend_weight = 1.0 - original_confidence
  │         if original confidence was high, AI has less influence
  │         if original confidence was low, AI takes over
  │      6. Audit.log(module, prompt_version, tools_called, latency, cost)
  │
  └── Exception during AI
         → original result passes through unchanged
         → error logged to audit
```

## Result Blending

```python
@dataclass
class BlendedResult:
    value: float | None        # blended score / multiplier
    confidence: float          # updated confidence
    source: str                # "deterministic" | "ai_refined" | "blended"

def blend(original: ModuleResult, ai: dict, ai_confidence: float) -> BlendedResult:
    w = max(0.1, min(0.9, 1.0 - original.confidence))

    if original.value is not None and ai.get("value") is not None:
        blended_value = original.value * (1 - w) + ai["value"] * w
    elif original.value is None:
        blended_value = ai.get("value")
    else:
        blended_value = original.value

    new_confidence = min(1.0, original.confidence + ai_confidence * w)

    return BlendedResult(
        value=blended_value,
        confidence=new_confidence,
        source="blended" if 0.2 < w < 0.8 else ("ai_refined" if w > 0.5 else "deterministic"),
    )
```

## Refinement Policy Configuration

```python
REFINEMENT_POLICY: list[RefinementRule] = [
    # M6: suspicious multi-word splits
    RefinementRule(
        module="m6",
        trigger=lambda ctx: ctx.get("word_count", 0) >= 4,
        prompt="m06_segmenter_disambiguate",
        tools=["word_break", "word_frequency", "valid_word"],
        max_cost=0.002,
    ),
    # M6: verify no_split is correct
    RefinementRule(
        module="m6",
        trigger=lambda ctx: ctx.get("m6_status") == "no_split",
        prompt="m06_segmenter_verify_nosplit",
        tools=["word_break", "valid_word"],
        max_cost=0.001,
    ),
    # M7: keyword popularity for unknown terms
    RefinementRule(
        module="m7",
        trigger=lambda ctx: ctx.get("domain_score", 100) < 10,
        prompt="m07_keyword_popularity",
        tools=["keyword_popularity", "word_frequency"],
        max_cost=0.001,
    ),
    # M8: commercial intent for unmapped words
    RefinementRule(
        module="m8",
        trigger=lambda ctx: ctx.get("tier") == "none",
        prompt="m08_cpc",
        tools=["cpc_lookup", "cpc_tier_rank"],
        max_cost=0.001,
    ),
    # M11: trademark risk beyond known marks
    RefinementRule(
        module="m11",
        trigger=lambda ctx: ctx.get("severity") == "none",
        prompt="m11_trademark",
        tools=["trademark_check", "known_trademark"],
        max_cost=0.001,
    ),
    # M13: confidence validation
    RefinementRule(
        module="m13",
        trigger=lambda ctx: ctx.get("completeness_ratio", 1.0) < 0.8,
        prompt="m13_confidence",
        tools=[],
        max_cost=0.0005,
    ),
    # M15: valuation cross-check
    RefinementRule(
        module="m15",
        trigger=lambda ctx: True,  # always check
        prompt="m15_pricing",
        tools=[],
        max_cost=0.001,
    ),
    # M16: brandability
    RefinementRule(
        module="m16",
        trigger=lambda ctx: True,  # always when brandable
        prompt="m16_brandability",
        tools=["vowel_ratio", "bigram_frequency"],
        max_cost=0.002,
    ),
]
```

## Cost Budget

The orchestrator enforces a per-domain AI budget:

```python
class CostController:
    def __init__(self, per_domain_budget: float = 0.01, daily_budget: float = 1.00):
        self.per_domain = per_domain_budget
        self.daily = daily_budget
        self.spent_today = 0.0

    def can_use(self, estimated_cost: float) -> bool:
        if self.spent_today + estimated_cost > self.daily:
            return False
        return estimated_cost <= self.per_domain

    def track(self, cost: float) -> None:
        self.spent_today += cost
```

Rules are ranked by cost-benefit. If the budget is tight, the orchestrator skips low-benefit rules first (M5, M16) and keeps high-benefit ones (M6, M8, M15).

## Error Handling

| Failure | Behavior |
|---|---|
| AI provider timeout (>10s) | Return original result, log WARNING |
| AI provider returns non-parseable response | Return original result, log ERROR |
| Tool execution raises exception | Skip that tool call, continue with others |
| Cost budget exhausted | Skip remaining refinement rules |
| Authentication failure (bad key) | Disable AI for this session, log CRITICAL |
| Circuit breaker open | All AI calls skipped, deterministic-only mode |

## Concurrency

The orchestrator can process module refinements in parallel when they don't depend on each other:

```
Phase 1 (parallel):
  M6 refinement (needs M6 output)
  M7 refinement (needs M7 output)

Phase 2 (parallel):
  M8 refinement (no dependency on M6/M7 AI results)
  M11 refinement (no dependency)

Phase 3:
  M13 refinement (needs all module statuses)

Phase 4:
  M15 refinement (needs final value)

Phase 5:
  M16 refinement (only if brandable)
```

## Implementation Files

```
ceche/infrastructure/ai/
├── orchestrator/
│   ├── __init__.py
│   ├── agent.py            # AgentOrchestrator main class
│   ├── policy.py           # RefinementPolicy, RefinementRule
│   ├── blender.py          # ResultBlender
│   ├── budget.py           # CostController
│   └── pipeline.py         # Pipeline hook into AppraisalEngine
```

## Best Practices

### Pipeline Integration
- The orchestrator must run AFTER all deterministic modules in a phase complete, not interleaved. This prevents race conditions where an AI-refined M6 result reaches M7 before the deterministic M7 has run.
- Never block the main appraisal loop on AI. Use `asyncio.wait_for(ai_call, timeout=10.0)` so a slow AI provider doesn't stall the entire pipeline.
- When AI is disabled (NoOp adapter), the orchestrator should short-circuit immediately and pass through all deterministic results with zero overhead. Add a single `if not self._ai_enabled: return` check at the entry point.

### Blending Strategy
- Never let AI fully override a high-confidence deterministic result. The blend weight `w` should be capped at 0.5 when original confidence >= 0.9. The formula: `w = min(0.5, 1.0 - original_confidence)`.
- When AI and deterministic results disagree by more than 2 standard deviations (relative to the module's normal output range), flag the result for human review rather than blindly blending. Add a `review_flagged: true` field to the blended result.
- For categorical outputs (M6 SINGLE vs SPLIT, M11 RISK level), blending doesn't apply. AI either confirms or overrides. If it overrides, the original is preserved in `data.original_severity` for audit.

### Cost Control
- Enforce the per-domain budget BEFORE making any AI calls. Compute the estimated cost of all triggered rules first, then decide which to run within budget.
- Rank rules by expected value: M6 (prevents bad segmentation) > M8 (adds CPC coverage) > M11 (trademark risk) > M16 (brandability polish) > M5 (pronounceability nuance) > M7 (keyword replacement). Skip low-rank rules when budget is tight.
- Track actual cost vs estimated cost. If actual regularly exceeds estimate by >50%, recalibrate the token estimates.

## Common Mistakes & How to Avoid Them

| Mistake | Why It Happens | Prevention |
|---|---|---|
| **AI call blocks the pipeline** | No timeout set, provider hangs | `asyncio.wait_for(..., timeout=10.0)` on every AI call |
| **Deterministic result replaced by bad AI output** | AI confidence was low but blend weight was high | Cap blend weight at 0.5 for high-confidence deterministic results |
| **Cost explodes on a single domain** | Per-domain budget not enforced | Check budget BEFORE calling AI, not after |
| **Rules fire when they shouldn't** | Trigger condition is too broad | Every rule must have a specific lambda trigger. Test triggers against known-good cases. |
| **Orchestrator calls AI for every module even when not needed** | All rules enabled by default | Default all rules to disabled. Enable only those proven to add value. |
| **AI results from a previous appraisal leak into the next one** | Shared mutable state | Reset the AI context dict between appraisals |

## Enterprise-Grade Implementation Checklist

- [ ] AI calls have 10-second timeout, non-blocking via asyncio.wait_for
- [ ] Short-circuit when AI disabled (NoOp adapter) — zero overhead
- [ ] Blend weight capped at 0.5 when deterministic confidence >= 0.9
- [ ] Per-domain budget enforced BEFORE any AI call
- [ ] Rules ranked by expected value; low-rank skipped when budget tight
- [ ] All rules default to disabled; individually enableable via config
- [ ] Categorical outputs (SINGLE/SPLIT, RISK tier) record original in data for audit
- [ ] Integration test: slow AI provider doesn't stall pipeline (returns deterministic result after timeout)
- [ ] Integration test: AI disabled produces identical output to running without AI layer
- [ ] Integration test: cost budget exhausted mid-domain → remaining rules skipped, prior results kept
- [ ] Integration test: AI context reset between appraisals (no cross-contamination)
