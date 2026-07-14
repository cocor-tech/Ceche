# TLD Score Table

## TLD Rankings (1–10 scale)

These 54 TLDs have custom scores. All other TLDs default to 0.2.

| Score | TLDs |
|---|---|
| **10** | .com |
| **9** | .net |
| **8.5** | .io, .ai |
| **8** | .co, .de, .edu, .org, .xxx |
| **7.5** | .app, .it, .xyz |
| **7** | .us, .tv, .me, .cc, .to, .tech |
| **6.5** | .world |
| **6** | .eu, .sh, .ca, .inc, .wiki, .pro, .space, .shop, .online, .info, .in |
| **5** | .asia, .africa, .gg, .tel, .news, .site |
| **4.5** | .ltd |
| **4** | .cloud, .co.uk, .blog, .fun, .it.com, .sport, .studio, .live |
| **3.5** | .art |
| **3** | .network, .lgbt, .bio |
| **2** | .agency, .lol, .one, .biz |
| **1** | .icu |
| **0.2** | everything else |

## What Determines TLD Worth

1. **Trust & universal recognition** — `.com` is the default. Users type `something.com` reflexively.
2. **Aftermarket liquidity** — resale frequency and median sale price.
3. **Renewal price vs perceived value** — `.io` costs $35/yr but brands pay it because the association (tech/startup) justifies the premium.
4. **Industry association** — `.ai` for AI companies, `.tv` for media, `.app` for apps. These create price floors within niches.
5. **SEO treatment & history** — legacy TLDs carry authority inertia.
6. **Registration restrictions** — `.de` requires a German address (creates scarcity).
7. **Hype cycle** — `.ai` is peaking now. `.io` peaked 2015–2022. Scores may shift quarterly.

## Weight Profiles Per TLD Tier

The TLD score determines which weight profile M15 uses for the non-TLD modules. Higher-scored TLDs favor scarcity factors; lower-scored TLDs favor commercial signals.

### Tier 10 (.com)

| Module | Weight | Notes |
|---|---|---|
| M4 Word count | 30 | Single word .com is the premium asset class |
| M3 Length | 20 | 3L/4L .com scarcity dominates pricing |
| M1 Age | 15 | Legacy matters |
| M7 Popularity | 10 | Keyword relevance |
| M8 CPC | 10 | Commercial intent |
| M12 History | 5 | Established sites |
| M5 Pronounceability | 5 | Brandability |
| M11 Trademark | 5 | Only as conflict detector |
| M10 Cross-TLD | 0 | .com is canonical, no penalty applies |
| **Total** | **100** | |

### Tier 8–9 (.net, .io, .ai, .co, .de, .edu, .org, .xxx)

| Module | Weight | Notes |
|---|---|---|
| M7 Popularity | 25 | Keyword relevance more important |
| M8 CPC | 20 | Commercial intent drives value |
| M4 Word count | 15 | Still benefits from single words |
| M3 Length | 10 | Less scarcity, shorter still better |
| M1 Age | 10 | |
| M5 Pronounceability | 10 | Brandability matters |
| M10 Cross-TLD | 5 | .com variant could outrank you |
| M12 History | 3 | |
| M11 Trademark | 2 | |
| **Total** | **100** | |

### Tier 6–7.5 (.app, .xyz, .us, .tv, .me, .cc, .to, .tech, .world, etc.)

| Module | Weight | Notes |
|---|---|---|
| M7 Popularity | 30 | Keyword is the main value driver |
| M8 CPC | 25 | |
| M5 Pronounceability | 15 | Memorable names matter on non-standard TLDs |
| M4 Word count | 10 | |
| M3 Length | 5 | |
| M10 Cross-TLD | 5 | .com competitor is a real threat |
| M1 Age | 5 | |
| M12 History | 3 | |
| M11 Trademark | 2 | |
| **Total** | **100** | |

### Tier 4–5 (.asia, .cloud, .co.uk, .blog, .news, .site, etc.)

| Module | Weight | Notes |
|---|---|---|
| M8 CPC | 30 | Commercial intent dominates |
| M7 Popularity | 25 | |
| M10 Cross-TLD | 15 | Strong .com variant is a major concern |
| M5 Pronounceability | 10 | |
| M4 Word count | 8 | |
| M3 Length | 5 | |
| M1 Age | 3 | |
| M11 Trademark | 2 | |
| M12 History | 2 | |
| **Total** | **100** | |

### Tier 1–3 (.icu, .biz, .one, .lol, .network, .art, etc.)

| Module | Weight | Notes |
|---|---|---|
| M8 CPC | 35 | Only commercial intent can save these |
| M7 Popularity | 25 | |
| M10 Cross-TLD | 20 | .com has all the value |
| M5 Pronounceability | 10 | |
| M4 Word count | 5 | |
| M3 Length | 3 | |
| M1 Age | 1 | |
| M11 Trademark | 1 | |
| M12 History | 0 | |
| **Total** | **100** | |

### Tier 0.2 (default — all unlisted TLDs)

| Module | Weight | Notes |
|---|---|---|
| M8 CPC | 40 | |
| M7 Popularity | 30 | |
| M10 Cross-TLD | 20 | |
| M5 Pronounceability | 5 | |
| M4 Word count | 3 | |
| M3 Length | 2 | |
| **Total** | **100** | |

## Brandable Fallback Profile

Activated when M6 returns `no_split` (no dictionary words found). Overrides the standard profile for the TLD tier:

| Module | Weight | Notes |
|---|---|---|
| M5 Pronounceability | 30 | Sound is everything for brandables |
| M16 Brandability | 25 | Letter patterns, syllable flow |
| M3 Length | 20 | Shorter is more brandable |
| M7 Popularity | 10 | Partial matches may still score |
| M8 CPC | 5 | |
| M2 TLD | 5 | .com brandable > .xyz brandable |
| M10 Cross-TLD | 3 | |
| M11 Trademark | 2 | |
| **Total** | **100** | |

## Data Storage

Stored in `ceche/data/tld_scores.json`:

```json
{
  "com": 10,
  "net": 9,
  "io": 8.5,
  "ai": 8.5,
  "co": 8,
  ...
  "icu": 1,
  "_default": 0.2
}
```
