# AI Enhancements

## Where AI Adds Value

Ceche's modular architecture is intentionally deterministic for most modules. Three specific areas benefit from AI assistance:

---

## 1. M6 — Segmenter Disambiguation

**Current limitation:** M6 uses a static word list + frequency-weighted DP algorithm. It can't handle context, slang, portmanteaus, or compound words that don't appear in its dictionary.

**AI improvement:** An LLM (or smaller fine-tuned model) reviews the domain string and top 3 DP candidates to select the best segmentation. It can recognize:
- Portmanteaus: "slack" → originally "searchable log of all conversation and knowledge" — a portmanteau, not "s"+"lack"
- Brand names: "google" → no valid English split (correctly no_split, brandable)
- Slang: "gonna", "wanna" → recognized as valid words even if not in formal dictionaries
- Industry-specific terms: "fintech", "edtech", "medtech" → valid compounds

**Implementation:**
- Use M6 DP as the fast first pass (cheap, always available)
- If confidence of the top split is low (<0.7), query AI for verification
- AI returns: chosen split + confidence score
- Cache the AI's decision via M14 (TTL: 30 days)

**Fallback:** If AI is unavailable, fall back to DP-only output (existing behavior).

---

## 2. M16 — Brandability Assessment

**Current limitation:** M16 uses rule-based scoring (syllable count, letter patterns, bigram frequency). This catches obvious patterns but misses the nuanced "does this sound like a real brand?" judgment that humans make instinctively.

**AI improvement:** An LLM evaluates the domain string as a potential brand name, answering:
- "Does this sound like a real company name or product?"
- "What industry does it evoke?" (tech, luxury, healthcare, media...)
- "Is it memorable? Easy to spell over the phone?"
- "Does it feel like existing successful brands?" (Google, Stripe, Zoom, Twilio)

**Training data:** Prompt the AI with known successful brand domains and their characteristics. Common patterns emerge:
- Short (5-7 chars) words ending in vowels
- Double letters (Zillow, McDonald's)
- -ify, -ly, -io, -ex, -r endings
- Plosive consonants (k, p, t, b, g) create memorability

**Example output:**

```
Domain: nekwasa
AI brandability: 7.5/10
  - 3 syllables, good flow
  - Vowel-rich (balanced vowel density)
  - No awkward consonant clusters
  - Feels like a tech startup or app name
  - Slightly exotic but memorable
  - Similar to: "Kawasaki" (truncated), "Nakasa" (variation)
```

**Integration:** M16 runs rule-based scoring first (fast, always on). If score is marginal (30–70 range), optionally query AI for refinement. AI score blends with rule-based score at 50/50 weight.

**Fallback:** If AI is unavailable, use rule-based score only.

---

## 3. M15 — Pricing Calibration

**Current limitation:** The multiplier curves and TLD base values are manually set starting points. They need calibration against real sales data to accurately reflect market reality.

**AI improvement:** Given a dataset of known domain sales with their Ceche module scores, an LLM or regression model can learn the optimal multiplier mappings.

**Process:**
1. Collect known domain sales with sale prices (NameBio NamePros posts, DNJournal articles, manual research)
2. Run each through Ceche, record every module's raw output
3. Feed the AI: "These are the module scores for car.com. The actual sale price was $185M. What multiplier curves produce this result?"
4. AI outputs calibrated multiplier tables that minimize error across the training set

```
Input:
  Domain: car.com
  Actual: $185,000,000
  Module scores:
     M4: 100  M3: 98  M7: 95  M1: 100  M8: 85
     M11: 100 M5: 98  M12: 100
  tld_base: $100

Output:
  Recommended multiplier adjustments:
    M7 >= 90  current: ×8  proposed: ×12
    M4 == 100 current: ×20 proposed: ×22
    M8 elite  current: ×5  proposed: ×8
```

**Result:** Over time, as more sales data is fed to the AI, Ceche's valuations converge toward market reality. The system learns which signals matter most for different asset classes.

**Privacy:** All calibration data stays local. No domain names are sent externally unless using a hosted AI API.

---

## AI Configuration

```toml
[ai]
provider = "none"            # "none", "openai", "anthropic", "local"
model = ""                   # model name (if applicable)
api_key = ""                 # API key
max_cost_per_appraisal = 0.01  # max AI cost per domain in dollars
enable_for_m6 = false        # enable AI segmenter refinement
enable_for_m16 = false       # enable AI brandability
enable_for_calibration = false # enable AI pricing calibration
```

Disabled by default. Each feature can be enabled independently.

## When NOT to Use AI

AI should NOT replace the deterministic modules:
- M1 RDAP: always use the API directly
- M2 TLD table: static lookup
- M3 Length: pure math
- M4 Word count: reads M6 output
- M8 CPC: static embedded map
- M9 Search: API call
- M10 Cross-TLD: RDAP + HTTP
- M11 Trademark: direct database queries
- M14 Cache: local SQLite

These modules are **faster, cheaper, and more reliable** as pure code. AI assists only where human-like judgment adds genuine value.
