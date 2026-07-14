# Ceche — Architecture Overview

## What Ceche Does

Ceche is a domain appraisal engine that evaluates any domain string — registered or unregistered — and produces a dollar value estimate. It uses 16 independent modules, each scoring a different dimension of a domain's worth. The outputs compound through a multiplier-based valuation model to produce realistic price ranges.

## Core Design Principles

1. **Unregistered domains get appraised too** — no silent zero-scoring. Every module returns a status alongside its value.
2. **Zero bias toward domains with existing history** — brandables, coinages, and never-registered strings are scored fairly through pronounceability and brandability signals.
3. **$0–$2/month operating budget** — entirely free-tier and self-hosted tooling. No paid APIs.
4. **Module-based architecture** — each signal is isolated. If one module fails (rate-limited, error), the rest of the pipeline continues.
5. **Multiplier-based valuation** — not linear percentages. Multipliers compound naturally to produce realistic dollar amounts across all price tiers.

## Pipeline Flow

```
Domain Input ("car.com")
        │
        ▼
┌──────────────────┐
│ Parse SLD + TLD  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ M14 — Cache     │
│ (check before   │
│  every call)    │
└────────┬─────────┘
         │
    ┌────┴──────────────────────────────┐
    │                                   │
    ▼                                   ▼
┌───────────┐                  ┌──────────────────┐
│ M1 — RDAP │                  │ M6 — Segmenter   │
│ (age,     │                  │ (word-break DP)  │
│ status)   │                  │ top segmentation │
└─────┬─────┘                  └────────┬─────────┘
      │                                │
      │                    ┌───────────┼───────────┐
      │                    ▼           ▼           ▼
      │              ┌──────────┐ ┌──────────┐ ┌──────────┐
      │              │ M4 —    │ │ M3 —    │ │ M5 —    │
      │              │ Word    │ │ Length  │ │ Pronounc│
      │              │ Count   │ │         │ │ ability │
      │              └──────────┘ └──────────┘ └──────────┘
      │                                │
      ▼                                ▼
┌───────────┐                  ┌──────────────────┐
│ M2 — TLD  │                  │ M7 — Keyword     │
│ Score     │                  │ Popularity       │
│ Table     │                  │ (pytrends+static)│
└─────┬─────┘                  └────────┬─────────┘
      │                                │
      ▼                                ▼
┌───────────┐                  ┌──────────────────┐
│ M10 —     │                  │ M8 — CPC         │
│ Cross-TLD │                  │ (static 5K map)  │
│ Check     │                  │                  │
└─────┬─────┘                  └────────┬─────────┘
      │                                │
      ▼                                ▼
┌───────────┐                  ┌──────────────────┐
│ M11 —     │                  │ M9 — Search      │
│ Trademark │                  │ Results          │
│ Check     │                  │ (CSE + Brave)    │
└─────┬─────┘                  └────────┬─────────┘
      │                                │
      ▼                                ▼
┌───────────┐                  ┌──────────────────┐
│ M12 —     │                  │ M16 — Brandability│
│ Backlink/ │                  │ (when M6 fails)  │
│ History/  │                  │                  │
│ Age       │                  │                  │
└─────┬─────┘                  └────────┬─────────┘
      │                                │
      └────────────┬───────────────────┘
                   │
                   ▼
          ┌────────────────┐
          │ M13 — Confid   │
          │ Flag + M15 —   │
          │ Pricing        │
          └────────┬───────┘
                   │
                   ▼
          ┌────────────────┐
          │ Final Output   │
          │ $ value + range│
          │ + confidence   │
          └────────────────┘
```

## Valuation Model

Ceche uses a **multiplier-based** valuation system:

```
final_value = tld_base × multiplier_m4 × multiplier_m3 × multiplier_m7 × ...
```

- `tld_base` = a base dollar amount determined by the TLD (e.g., .com = $100, .io = $30, .icu = $1)
- Each module produces a multiplier (e.g., single word = ×20, 3 chars = ×15, high CPC = ×5)
- Multipliers **compound** — producing realistic spreads from $1 to $100M+ naturally
- No linear percentage scoring, no artificial caps or ceilings

## TLD Tier Weight Profiles

Each TLD's score (1–10) determines which weight profile applies. Higher-scored TLDs use profiles that favor scarcity factors (length, word count). Lower-scored TLDs use profiles that favor commercial signals (CPC, keyword popularity).

See `03-tld-score-table.md` for the full weight profiles per tier.

## Module Status Reporting

Every module returns:
- `score`: float or null (if inapplicable)
- `status`: `success` | `quota_exceeded` | `not_found` | `error` | `skipped`
- `confidence`: float 0–1

M13 aggregates these into the final confidence flag.
