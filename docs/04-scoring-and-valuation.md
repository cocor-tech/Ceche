# Scoring & Valuation

## The Multiplier Model

Ceche uses a **multiplier-based** valuation system instead of linear percentage scoring. Each module contributes a multiplier, and the final value is their product:

```
final_value = tld_base × m4_mult × m3_mult × m7_mult × m8_mult × m5_mult × m1_mult × m12_mult × m11_mult × m16_mult
```

- `tld_base` = base dollar amount for the TLD (set per TLD tier)
- Each module's `value` is mapped to a multiplier (see per-module specs)
- Missing modules (null) are **omitted** — they don't multiply by 1 or 0
- Penalty modules (M10, M11 when triggered) apply as ×0.1–×0.9 reductions

## TLD Base Values

The base value represents the starting worth of a domain on that TLD before any other signals are applied.

| TLD Tier | Example TLDs | tld_base |
|---|---|---|
| 10 | .com | $100 |
| 8–9 | .net, .io, .ai, .co, .de, .org | $50 |
| 7–7.5 | .app, .xyz, .us, .tv, .me, .tech | $30 |
| 6–6.5 | .world, .eu, .sh, .ca, .inc, .wiki | $20 |
| 4–5 | .cloud, .blog, .news, .site, .asia | $10 |
| 1–3 | .icu, .biz, .one, .network, .art | $5 |
| 0.2 | all others | $2 |

## Module-to-Multiplier Mappings

### M1 — Age
| Age (years) | Multiplier |
|---|---|
| 20+ | ×3.0 |
| 10–20 | ×2.0 |
| 5–10 | ×1.5 |
| 1–5 | ×1.2 |
| <1 | ×1.0 |
| null (unregistered) | omitted |

### M3 — Length
| Score | Chars | Multiplier |
|---|---|---|
| >= 95 | 1–3 | ×15 |
| >= 75 | 4–5 | ×8 |
| >= 50 | 6–7 | ×2 |
| >= 25 | 8–10 | ×1.2 |
| < 25 | 11+ | ×1.0 |

### M4 — Word Count
| Words | Score | Multiplier |
|---|---|---|
| 1 | 100 | ×20 |
| 2 | 60 | ×3 |
| 3 | 35 | ×1.5 |
| 4+ | 5–20 | ×1.0 |
| null (no split) | — | omitted |

### M5 — Pronounceability
| Score | Multiplier |
|---|---|
| >= 90 | ×2.0 |
| >= 70 | ×1.5 |
| >= 40 | ×1.2 |
| < 40 | ×1.0 |

### M7 — Keyword Popularity
| Score | Multiplier |
|---|---|
| >= 90 | ×8 |
| >= 70 | ×5 |
| >= 50 | ×3 |
| >= 30 | ×2 |
| >= 10 | ×1.5 |
| < 10 or null | ×1.0 |

### M8 — CPC Tier
| Tier | Multiplier |
|---|---|
| Elite | ×5 |
| High | ×3 |
| Medium-High | ×2.5 |
| Medium | ×2 |
| Low | ×1.5 |
| Informational / None / null | ×1.0 |

### M9 — Search Results
| Result Count | Multiplier |
|---|---|
| 10,000+ | ×5 |
| 1,000+ | ×3 |
| 100+ | ×2 |
| 10+ | ×1.3 |
| <10 / null | ×1.0 |

### M10 — Cross-TLD Conflict
| Situation | Multiplier |
|---|---|
| No competing TLD active | ×1.0 |
| Competing .com active (non-.com domain) | ×0.5 |
| Appraising a .com | ×1.0 (always) |

### M11 — Trademark Conflict
| Situation | Multiplier |
|---|---|
| No conflict | ×1.0 |
| Partial match (word shared with a mark) | ×0.5 |
| Exact brand match, not the owner | ×0.1 |
| Exact brand match, IS the owner | ×1.0 |

### M12 — History & Authority
Blended score:
| Combined score | Multiplier |
|---|---|
| >= 90 (established site) | ×3 |
| >= 50 (some history) | ×2 |
| >= 20 (minimal) | ×1.2 |
| < 20 or null | ×1.0 |

**Parked domain override:**
- If parked_flag is true and domain is registered → multiplier capped at ×0.5
- If domain is unregistered → null (omitted)

### M16 — Brandability
| Score | Multiplier |
|---|---|
| >= 80 (high brandable) | ×8 |
| >= 60 | ×5 |
| >= 40 | ×3 |
| >= 20 | ×2 |
| < 20 | ×1 |
| null (M6 found split) | omitted |

## Worked Examples

### abc.com

```
TLD: .com (tier 10)
tld_base: $100

M4 — 1 word           → ×20
M3 — 3 chars          → ×15
M7 — "abc" very high  → ×8
M8 — low CPC           → ×1
M11 — no conflict      → ×1
M5 — pronounceable     → ×2
M1 — 30+ years         → ×3
M12 — extensive        → ×3

Product = 20 × 15 × 8 × 1 × 1 × 2 × 3 × 3 = 43,200
Value   = $100 × 43,200 = $4,320,000
```

### car.com

```
TLD: .com (tier 10)
tld_base: $100

M4 — 1 word           → ×20
M3 — 3 chars          → ×15
M7 — "car" very high  → ×8
M8 — auto CPC Elite   → ×5
M11 — no conflict      → ×1
M5 — pronounceable     → ×2
M1 — 30+ years         → ×3
M12 — extensive        → ×3

Product = 20 × 15 × 8 × 5 × 1 × 2 × 3 × 3 = 216,000
Value   = $100 × 216,000 = $21,600,000
```

### nekwasa.com (brandable, unregistered)

```
TLD: .com (tier 10)
tld_base: $100

M6 — no_split → M4/M7/M8 all omitted, M16 activates

M3 — 7 chars             → ×2
M5 — pronounceable       → ×1.5
M16 — brandable          → ×5
M11 — no conflict         → ×1
M1 — unregistered         → omitted
M12 — unregistered        → omitted

Product = 2 × 1.5 × 5 × 1 = 15
Value   = $100 × 15 = $1,500
```

### sadmecry.com (multi-word, unregistered)

```
TLD: .com (tier 10)
tld_base: $100

M6 → "sad" + "me" + "cry" (3 words)

M4 — 3 words            → ×1.5
M3 — 8 chars            → ×1.2
M7 — "me" popular       → ×3
M8 — informational       → ×1
M11 — no conflict         → ×1
M5 — pronounceable       → ×1.5
M1 — unregistered         → omitted
M12 — unregistered        → omitted

Product = 1.5 × 1.2 × 3 × 1 × 1 × 1.5 = 8.1
Value   = $100 × 8.1 = $810
```

### godaddy.icu (low-tier TLD, unregistered)

```
TLD: .icu (tier 1)
tld_base: $5

M6 → "go" + "daddy" (2 words)

M4 — 2 words            → ×3
M3 — 6 chars            → ×2
M7 — "go"/"daddy" high  → ×5
M8 — informational       → ×1
M11 — trademark conflict  → ×0.1 (GoDaddy is a registered trademark)
M5 — pronounceable       → ×2
M1 — unregistered         → omitted
M12 — unregistered        → omitted
M10 — .com exists active  → ×0.5 (non-.com domain)

Product = 3 × 2 × 5 × 1 × 0.1 × 2 × 0.5 = 3
Value   = $5 × 3 = $15
```

## Confidence & Range

```
completeness_ratio = modules_with_data / applicable_modules

range_low  = final_value × (1 - (1 - completeness_ratio) × 0.5)
range_high = final_value × (1 + (1 - completeness_ratio) × 0.5)
```

### Example: abc.com (all modules available, high confidence)

```
completeness_ratio = 1.0 (8/8 modules returned data)
range_low  = $4,320,000 × (1 - 0) = $4,320,000
range_high = $4,320,000 × (1 + 0) = $4,320,000
```

A perfect completeness ratio produces a single value (no range widening).

### Example: nekwasa.com (only 5 of 8 applicable modules returned data)

```
completeness_ratio = 5/8 = 0.625
range_low  = $1,500 × (1 - 0.375 × 0.5) = $1,500 × 0.8125 = $1,219
range_high = $1,500 × (1 + 0.375 × 0.5) = $1,500 × 1.1875 = $1,781
```

Missing signals widen the range, signaling reduced confidence.

## Note on Calibration

The multipliers in this document are starting defaults. They should be calibrated against known domain sales over time. The calibration process:

1. Appraise a domain with known sale price
2. Compare the Ceche output to the actual price
3. Adjust individual multiplier curves until the system produces outputs that match market reality
4. Repeat across multiple asset classes (3L .com, dictionary word .com, brandable .com, keyword .io, etc.)
