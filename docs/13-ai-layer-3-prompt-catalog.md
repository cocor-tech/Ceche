# Layer 3 — Prompt Catalog

## Overview

The prompt catalog contains version-controlled, model-agnostic prompts for each module. Every prompt includes few-shot examples, output format constraints, and confidence scoring. The AI agent selects the appropriate prompt based on which module needs refinement, injects tool call results as context, and returns a structured, parseable response.

## Architecture

```
ceche/infrastructure/ai/prompts/
├── __init__.py
├── base.py              # Prompt dataclass + renderer
├── m05_pronounce.py     # "Does this sound like a real word?"
├── m06_segmenter.py     # "Is this SINGLE or SPLIT into real words?"
├── m07_keyword.py       # "What is the search popularity of this term?"
├── m08_cpc.py           # "What is the commercial intent tier?"
├── m11_trademark.py     # "Is this term a likely registered trademark?"
├── m13_confidence.py    # "What is the true confidence across these modules?"
├── m15_pricing.py       # "Is this valuation reasonable for the domain class?"
├── m16_brandability.py  # "Rate this coinage as a potential brand name."
```

## Prompt Dataclass

```python
@dataclass
class Prompt:
    id: str                          # "m06_segmenter_disambiguate"
    version: str                     # "1.0.0"
    module: str                      # "m6"
    purpose: str                     # "Disambiguate word-break results"
    system: str                      # System message (role, tone, format)
    user_template: str               # Template with {variables}
    examples: list[PromptExample]    # Few-shot examples
    output_format: OutputFormat      # Expected response structure
    tools_allowed: list[str]         # Tool names the agent may call
    max_tokens: int                  # Response token limit
    temperature: float               # 0.0–1.0
```

## Prompt Catalog

### M5 — Pronounceability Assessment

**Trigger:** Score < 70 (low confidence) or consonant cluster >= 4

**Purpose:** AI evaluates whether a non-English string still sounds like a plausible word. Some strings (like German or Japanese coinages) have consonant clusters that sound natural despite failing English phonetic rules.

**Prompt:**

```
System:
You are a phonetics expert evaluating domain name pronounceability.
Consider English, common European, and East Asian phonetic patterns.
Respond ONLY with: SCORE:<0-100> CONFIDENCE:<0.0-1.0>

User:
String: {sld}
Vowel ratio: {vowel_ratio}
Max consonant cluster: {max_cluster}
Bigram score: {bigram_score}/100
Current pronounceability score: {current_score}/100

Is this string plausibly pronounceable as a brand name?
Respond with: SCORE:XX CONFIDENCE:XX
```

**Few-shot examples:**

```
"svelte"  → SCORE:92 CONFIDENCE:0.9   (borrowed word, sounds natural)
"fjfbfj"  → SCORE:5  CONFIDENCE:0.95  (unpronounceable)
"kirin"   → SCORE:85 CONFIDENCE:0.8   (Japanese origin, still pronounceable)
"borsch"  → SCORE:78 CONFIDENCE:0.7   (consonant cluster but recognizable)
```

### M6 — Segmenter Disambiguation

**Trigger A:** DP returns 4+ word split (likely false positive)

**Purpose:** AI determines whether a multi-word split is correct or if the domain should be treated as a single brandable. Prevents "gojominitia" → 6-word garbage split.

**Prompt A:**

```
System:
You are a domain name segmentation expert. Given a string and its
potential word splits, determine if the split is valid or if the
string should be treated as a SINGLE brandable coinage.

Rules:
- SINGLE if the split uses extremely short/rare words (≤2 letters)
- SINGLE if the domain reads as a made-up brand name
- SPLIT:word1+word2 if the words are genuine and the split is natural
- Respond ONLY with: SINGLE or SPLIT:word1+word2

User:
String: {sld}
Potential split: {split}
Word frequencies: {frequencies}

Is this a valid word split or a SINGLE brandable?
```

**Few-shot examples:**

```
"gojominitia" | "go+jo+min+it+i+a" → SINGLE
"topinsurance" | "top+insurance"   → SPLIT:top+insurance
"bestcar" | "best+car"             → SPLIT:best+car
"nekwasa" | None (no split found)  → SINGLE
```

**Trigger B:** DP returns no_split (verify it's truly unsegmentable)

**Prompt B:**

```
String: {sld}
No valid segmentation found by DP.

Could this string be broken into any real English words?
Consider compound words, portmanteaus, and slang.
Respond ONLY with: SINGLE or SPLIT:word1+word2
```

### M7 — Keyword Popularity Estimation

**Trigger:** pytrends fails AND static adapter returns score < 10

**Purpose:** AI estimates search popularity for unknown terms by reasoning about the word's meaning, commonality, and search intent.

**Prompt:**

```
System:
You are a search trend analyst. Estimate how popular a search term
would be on a 0-100 scale relative to all English search terms.
Consider: is this a common word, a niche term, or gibberish?

Respond ONLY with: SCORE:<0-100> CONFIDENCE:<0.0-1.0> CATEGORY:<category>

Categories: VERY_HIGH(80-100), HIGH(60-80), MEDIUM(30-60), LOW(10-30), VERY_LOW(0-10)

User:
Term: {word}
Word frequency (written text): {freq}
Word length: {length}

Estimate search popularity score and category.
```

**Few-shot examples:**

```
"insurance"  → SCORE:95 CONFIDENCE:0.95 CATEGORY:VERY_HIGH
"fjfbfj"     → SCORE:0  CONFIDENCE:0.99 CATEGORY:VERY_LOW
"cryptoverse" → SCORE:25 CONFIDENCE:0.6 CATEGORY:LOW (niche crypto term)
"plumber"    → SCORE:65 CONFIDENCE:0.8 CATEGORY:HIGH
```

### M8 — Commercial Intent Classification

**Trigger:** Word not found in embedded CPC map (tier = "none")

**Purpose:** AI assesses the commercial intent of a word — would advertisers pay to bid on this keyword? Classifies into the same tier system as the CPC map.

**Prompt:**

```
System:
You are a paid search advertising expert. Classify terms by their
commercial intent — how much advertisers would pay per click.

Tiers: ELITE($50+), HIGH($20-50), MEDIUM_HIGH($10-20), MEDIUM($3-10),
       LOW($1-3), INFORMATIONAL($0-1), NONE($0)

Respond ONLY with: TIER:<tier> CONFIDENCE:<0.0-1.0> REASON:<one sentence>

User:
Term: {word}
Current classification: not in CPC map (default NONE)

What is the commercial intent of this term?
```

**Few-shot examples:**

```
"mesothelioma"  → TIER:ELITE CONFIDENCE:0.95 REASON:Legal/medical term with high lawsuit advertising value
"sad"           → TIER:INFORMATIONAL CONFIDENCE:0.9 REASON:Emotional term, rarely monetized via search ads
"car"           → TIER:MEDIUM_HIGH CONFIDENCE:0.85 REASON:Auto industry term with high commercial search volume
"nekwasa"       → TIER:NONE CONFIDENCE:0.99 REASON:Gibberish, no search advertising value
```

### M11 — Trademark Risk Assessment

**Trigger:** Word not in USPTO known-marks list AND no exact match found

**Purpose:** AI assesses whether a term is likely to be a registered trademark or could be confused with one. Covers trademarks not in the curated 90-brand list.

**Prompt:**

```
System:
You are a trademark law analyst. Assess whether a term is likely
to be a registered trademark or could infringe on one.

Risk levels: EXACT(matches a known mark), HIGH(likely trademark),
MEDIUM(could be confused), LOW(unlikely trademark), NONE(generic)

Respond ONLY with: RISK:<level> CONFIDENCE:<0.0-1.0> NOTE:<one sentence>

User:
Term: {word}
Domain type: single word on .com

Assess trademark risk.
```

**Few-shot examples:**

```
"disney"    → RISK:EXACT CONFIDENCE:1.0 NOTE:Registered trademark of Disney Enterprises
"iphone"    → RISK:HIGH CONFIDENCE:0.95 NOTE:Likely infringes Apple's iPhone trademark
"car"       → RISK:NONE CONFIDENCE:0.99 NOTE:Generic dictionary word, not trademarkable alone
"zylo"      → RISK:LOW CONFIDENCE:0.6 NOTE:Could exist as a small brand but no major known mark
```

### M13 — Confidence Validation

**Trigger:** Completeness ratio < 0.8

**Purpose:** AI cross-checks module statuses to determine if missing signals truly impair the valuation or if the domain type means some signals are naturally absent.

**Prompt:**

```
System:
You are a domain appraisal quality auditor. Given per-module statuses,
determine the true confidence level of this appraisal.

Respond ONLY with: LABEL:<high|medium|low|very_low> REASON:<one sentence>
```

### M15 — Valuation Cross-Check

**Trigger:** Estimated value outside expected range for domain class

**Purpose:** AI compares the valuation to known comparable sales in the domain market. Flags over/under-valued domains for manual review.

**Prompt:**

```
System:
You are a domain valuation expert familiar with aftermarket sales.
Given a domain's characteristics and computed value, assess whether
the valuation is reasonable.

Respond ONLY with: ASSESSMENT:<reasonable|overvalued|undervalued>
ADJUSTED:<suggested_value or "none"> REASON:<one sentence>
```

### M16 — Brandability Assessment

**Trigger:** Always when M6 returns no_split (brandable coinage)

**Purpose:** AI evaluates made-up words as potential brand names. Scores memorability, industry association, phonetic appeal, and startup naming potential.

**Prompt:**

```
System:
You are a brand naming expert. Rate this coinage as a potential
brand name (product, company, or app). Score 0-100.

Consider: memorability, ease of spelling, phonetic appeal,
industry association, startup naming trends.

Respond ONLY with: SCORE:<0-100> CONFIDENCE:<0.0-1.0>
INDUSTRY:<tech|health|finance|media|consumer|generic|none>

User:
String: {sld}
Length: {length}
Syllable count: {syllables}
Current brandability score: {current_score}/100

Rate as a brand name.
```

**Few-shot examples:**

```
"nekowi"   → SCORE:78 CONFIDENCE:0.8 INDUSTRY:tech
"vello"    → SCORE:72 CONFIDENCE:0.75 INDUSTRY:consumer
"yotop"    → SCORE:45 CONFIDENCE:0.6 INDUSTRY:generic
"fjfbfj"   → SCORE:3  CONFIDENCE:0.95 INDUSTRY:none
```

## Output Parsing

Every prompt response is parsed with a robust extractor:

```python
def parse_prompt_response(prompt_id: str, raw: str) -> dict:
    """
    Parse structured output from AI responses.
    Handles: SCORE:XX, TIER:XX, RISK:XX, SINGLE/SPLIT, etc.
    Falls back to None/null on parse failure.
    """
```

Each prompt type has its own parser:
- `SCORE:<int> CONFIDENCE:<float>` → `{"score": int, "confidence": float}`
- `SINGLE` / `SPLIT:word1+word2` → `{"decision": "single" | "split", "words": [...]}`
- `TIER:<tier>` → `{"tier": str}`

## Version Control

Prompts are versioned in Git:

```python
# Each prompt file exports a versioned instance
M06_DISAMBIGUATE_V1 = Prompt(
    id="m06_segmenter_disambiguate",
    version="1.0.0",
    ...
)
```

When a prompt is updated, the version increments. The audit log records which prompt version was used for each AI call.

## Implementation Files

```
ceche/infrastructure/ai/prompts/
├── __init__.py
├── base.py              # Prompt dataclass, PromptExample, OutputFormat
├── parser.py            # Response parser for each prompt type
├── m05_pronounce.py
├── m06_segmenter.py
├── m07_keyword.py
├── m08_cpc.py
├── m11_trademark.py
├── m13_confidence.py
├── m15_pricing.py
├── m16_brandability.py
└── catalog.py           # Registry of all prompts by trigger condition
```
