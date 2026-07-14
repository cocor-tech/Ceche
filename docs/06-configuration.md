# Configuration

Ceche is configured via a YAML/TOML file at `~/.config/ceche/config.toml` or a local `ceche.toml` in the project root. The local file overrides the global one.

## Configuration File

### Full Example

```toml
# ceche.toml

[cache]
path = "ceche/cache/cache.db"
fresh = false

[tld_base]
# Base dollar values per TLD tier
tier_10 = 100    # .com
tier_09 = 50     # .net
tier_08 = 50     # .co, .de, .edu, .org, .xxx
tier_075 = 30    # .app, .it, .xyz
tier_07 = 30     # .us, .tv, .me, .cc, .to, .tech
tier_065 = 20    # .world
tier_06 = 20     # .eu, .sh, .ca, .inc, .wiki, .pro, .space, etc.
tier_05 = 10     # .asia, .africa, .gg, .tel, .news, .site
tier_045 = 10    # .ltd
tier_04 = 10     # .cloud, .co.uk, .blog, .fun, etc.
tier_035 = 5     # .art
tier_03 = 5      # .network, .lgbt, .bio
tier_02 = 5      # .agency, .lol, .one, .biz
tier_01 = 5      # .icu
tier_00 = 2      # all others (0.2)

[api_keys]
# All are optional — modules degrade gracefully without them
google_cse_key = ""        # for M9 (100 free queries/day)
brave_search_key = ""       # for M9 backup (~1000 free queries/month)
openpagerank_key = ""       # for M12 (30K free domains/month)

[module_defaults]
m9_primary = "google"       # or "brave"
m9_backup = "brave"         # or null to disable backup
m6_wordlist = "default"     # or "extended" for larger word list
m5_bigram_data = "default"  # embedded, no config needed

[output]
format = "json"             # json, table, or pretty
include_raw_data = false    # include per-module raw data in output
```

## Environment Variables

For sensitive values (API keys), environment variables override the config file:

| Variable | Overrides |
|---|---|
| `CECHE_GOOGLE_CSE_KEY` | `api_keys.google_cse_key` |
| `CECHE_BRAVE_KEY` | `api_keys.brave_search_key` |
| `CECHE_OPR_KEY` | `api_keys.openpagerank_key` |
| `CECHE_CACHE_PATH` | `cache.path` |
| `CECHE_FRESH` | `cache.fresh` |

## CLI Overrides

```
ceche appraise example.com                    # defaults
ceche appraise example.com --fresh             # bypass cache
ceche appraise example.com --format table      # table output
ceche appraise example.com --include-raw       # full data dump
ceche appraise example.com --config ./my.toml  # custom config
```

## Multi-Domain Mode

```
ceche appraise domains.txt                     # batch from file
ceche appraise example.com car.com nekwasa.com # multiple domains
```

Output aggregates all results with per-domain breakdowns.

## Module Toggling

```
ceche appraise example.com --skip m8,m12       # skip specific modules
ceche appraise example.com --only m1,m3,m5     # run only specific modules
```

Useful for debugging individual module behavior or when certain API quotas are exhausted.
