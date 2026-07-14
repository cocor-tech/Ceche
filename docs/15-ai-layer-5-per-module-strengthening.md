# Layer 5 — Per-Module Strengthening

## Overview

Each of the 8 AI-enhanced modules gets a dedicated `_ai_refine()` method. This method is called by the orchestrator after the deterministic run completes. It receives the original result, calls AI with module-specific prompts and tools, and returns a blended refinement.

The deterministic path is never modified. The AI path is additive — enabled per-module via config, invoked by the orchestrator, and blended into the pipeline result.

## Module Refinement Specifications

### M5 — Pronounceability

**Current:** Rule-based scoring using vowel density, consonant clusters, and bigram frequency. Struggles with non-English phonetic patterns (German "borsch", Japanese "kirin", Slavic "svelte").

| Aspect | Detail |
|---|---|
| **Trigger** | Score < 70 OR max_consonant_cluster >= 4 |
| **Prompt** | `m05_pronounce_assessment` |
| **Tools** | `vowel_ratio`, `max_consonant_cluster`, `bigram_frequency` |
| **Blend** | `ai_score * 0.5 + deterministic_score * 0.5` when triggered |
| **Cost** | ~$0.0005 per call |

**Value:** Handles non-English strings that English phonetic rules classify as unpronounceable but are perfectly natural words.

---

### M6 — Segmenter

**Current:** Wordfreq-based DP word-break. Produces false positive splits (4+ word garbage like "gojominitia" → 6 fragments). No context awareness.

| Aspect | Detail |
|---|---|
| **Trigger A** | `word_count >= 4` (suspicious multi-word split) |
| **Prompt** | `m06_disambiguate_split` |
| **Tools** | `word_break`, `word_frequency`, `valid_word` |
| **Blend** | AI overrides when `SINGLE`; keeps split when `SPLIT:x+y` |
| **Trigger B** | `status == "no_split"` (verify truly unsegmentable) |
| **Prompt** | `m06_verify_nosplit` |
| **Tools** | `word_break`, `valid_word` |
| **Cost** | ~$0.001 per call |

**Value:** Eliminates the #1 source of bad valuations — nonsense word splits. Catches portmanteaus and brandable coinages that wordfreq mistakes for multi-word compounds.

---

### M7 — Keyword Popularity

**Current:** pytrends (fragile) + static wordfreq-based fallback. The static fallback measures written text frequency, not search popularity. "insurance" gets score 6.1 despite being a top-100 search term.

| Aspect | Detail |
|---|---|
| **Trigger** | `domain_score < 10` AND `source == "static"` (both primary and fallback failed) |
| **Prompt** | `m07_keyword_popularity` |
| **Tools** | `keyword_popularity`, `word_frequency` |
| **Blend** | `max(ai_score, deterministic_score)` — take the higher |
| **Cost** | ~$0.0005 per word |

**Value:** Provides realistic search popularity estimates when pytrends is rate-limited and wordfreq underestimates niche terms.

---

### M8 — CPC / Commercial Intent

**Current:** 900-word static CPC map. Unknown words default to "none" (×1.0). "car" is mapped to "medium_high", but "cloud" was mapped to "high" (actually borderline), and thousands of commercial terms are unmapped.

| Aspect | Detail |
|---|---|
| **Trigger** | `tier == "none"` (word not in CPC map) |
| **Prompt** | `m08_cpc_classify` |
| **Tools** | `cpc_lookup`, `cpc_tier_rank` |
| **Blend** | AI tier overrides deterministic tier when confidence > 0.7 |
| **Cost** | ~$0.0005 per word |

**Value:** Expands CPC coverage from 900 to effectively unlimited. AI classifies any word's commercial intent by reasoning about the term's industry and advertising value.

---

### M11 — Trademark Risk

**Current:** 90-brand static known-marks list. Only catches major global brands. Thousands of registered trademarks pass through as "none."

| Aspect | Detail |
|---|---|
| **Trigger** | `severity == "none"` (no match in known marks) |
| **Prompt** | `m11_trademark_risk` |
| **Tools** | `trademark_check`, `known_trademark` |
| **Blend** | AI risk `HIGH` or `EXACT` → override deterministic; `LOW` → keep original |
| **Cost** | ~$0.0005 per word |

**Value:** Catches trademark risks beyond the 90-brand curated list. Flags terms like "iphone" (Apple), "playstation" (Sony), and thousands more.

---

### M13 — Confidence Validation

**Current:** Pure ratio — `modules_with_data / applicable_modules`. Doesn't account for domain type (unregistered naturally missing M1/M12) or signal quality.

| Aspect | Detail |
|---|---|
| **Trigger** | `completeness_ratio < 0.8` |
| **Prompt** | `m13_confidence_validate` |
| **Tools** | None (meta-analysis only) |
| **Blend** | AI confidence label overrides deterministic label |
| **Cost** | ~$0.0003 per call |

**Value:** Distinguishes "data missing because domain is unregistered" from "data missing because APIs failed." Provides a true confidence assessment.

---

### M15 — Pricing Cross-Check

**Current:** Formula-driven valuation based on scarcity base × quality factors. No market validation.

| Aspect | Detail |
|---|---|
| **Trigger** | Always (every appraisal) |
| **Prompt** | `m15_pricing_check` |
| **Tools** | None (reasoning over existing data) |
| **Blend** | AI suggests adjustments; orchestrator applies as score modifier (±20%) |
| **Cost** | ~$0.001 per call |

**Value:** Cross-checks formula-driven valuations against AI's knowledge of comparable domain sales. Flags domains that are significantly over/under-valued.

---

### M16 — Brandability

**Current:** Rule-based scoring using syllable count, letter patterns, and bigram frequency. No understanding of industry association, naming trends, or startup conventions.

| Aspect | Detail |
|---|---|
| **Trigger** | Always when M6 returns no_split |
| **Prompt** | `m16_brandability` |
| **Tools** | `vowel_ratio`, `bigram_frequency`, `max_consonant_cluster` |
| **Blend** | `ai_score * 0.6 + deterministic_score * 0.4` |
| **Cost** | ~$0.001 per call |

**Value:** Adds industry context (tech vs health vs consumer), startup naming trend awareness, and phonetic appeal assessment beyond pattern matching.

---

## Enabling Per-Module AI

```toml
# ceche.toml
[ai]
provider = "openai"
model = "gpt-4o-mini"

[ai.modules]
m5 = true   # Pronounceability refinement
m6 = true   # Segmenter disambiguation
m7 = true   # Keyword popularity estimation
m8 = true   # CPC classification
m11 = true  # Trademark risk assessment
m13 = true  # Confidence validation
m15 = true  # Pricing cross-check
m16 = true  # Brandability assessment
```

All disabled by default. Each module independently togglable. The system runs fully deterministically with zero AI cost when all are disabled.

## Expected Impact

| Scenario | Before AI | After AI | Why |
|---|---|---|---|
| "gojominitia.com" | $930 (6-word split) | $3K–$5K (brandable) | M6 AI catches false split |
| "cryptoverse.com" | $1K (no CPC) | $5K–$10K (medium CPC) | M8 AI classifies commercial intent |
| Untrademarked brand .com | $50K (no penalty) | $5K–$20K (TM caution) | M11 AI detects unlisted marks |
| Unregistered domain | "low" confidence | "medium" confidence | M13 AI understands domain type |

## Implementation Per Module

Each module gets a method structure:

```python
class M6Segmenter(BaseModule):
    def __init__(self, ai: AIPort | None = None) -> None:
        self._ai = ai              # AI port for refinement
        super().__init__()

    async def run(self, context):
        # 1. Always run deterministically
        result = await self._deterministic_run(context)

        # 2. If AI is enabled and result is low-confidence, refine
        if self._ai and self._should_refine(result):
            refined = await self._ai_refine(result, context)
            return refined

        return result

    async def _ai_refine(self, original, context):
        # Module-specific AI refinement logic
        ...
```

## Implementation Files

```
ceche/domain/modules/
├── m05_pronounceability.py    # +_ai_refine method
├── m06_segmenter.py           # +_ai_refine (existing, expand)
├── m07_keyword_popularity.py  # +_ai_refine method
├── m08_cpc.py                 # +_ai_refine method
├── m11_trademark.py          # +_ai_refine method
├── m13_confidence.py         # +_ai_refine method
├── m15_pricing.py            # +_ai_refine method
├── m16_brandability.py       # +_ai_refine method
```
