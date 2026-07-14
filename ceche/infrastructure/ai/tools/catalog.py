from __future__ import annotations

from wordfreq import word_frequency

from ceche.infrastructure.ai.tools.definition import ToolDefinition, ToolParam, ToolReturn
from ceche.infrastructure.ai.tools.registry import ToolRegistry

_MIN_FREQ = 1e-5
_MIN_WORD_LEN = 2
_SINGLE_CHAR_WORDS = frozenset({"a", "i"})


def _is_valid_word(word: str) -> bool:
    if len(word) < _MIN_WORD_LEN and word not in _SINGLE_CHAR_WORDS:
        return False
    f = word_frequency(word, "en")
    return bool(f > 0 and f >= _MIN_FREQ)


def _build_catalog() -> ToolRegistry:
    registry = ToolRegistry()

    # ── M1: RDAP / Registration ──
    registry.register(
        ToolDefinition(
            name="word_frequency",
            description="Get wordfreq frequency for any English word. Returns float 0.0-1.0.",
            parameters=[ToolParam(name="word", type="str", description="The word to look up")],
            returns=ToolReturn(type="float"),
            fn=lambda word: word_frequency(word, "en"),
            module="m6",
            cost=0.00001,
            cacheable=True,
        )
    )

    # ── M6: Segmenter ──
    registry.register(
        ToolDefinition(
            name="valid_word",
            description="Check if a word passes the frequency threshold for being real English.",
            parameters=[ToolParam(name="word", type="str", description="The word to check")],
            returns=ToolReturn(type="bool"),
            fn=_is_valid_word,
            module="m6",
            cost=0.00001,
            cacheable=True,
        )
    )

    # ── M5: Pronounceability helpers ──
    registry.register(
        ToolDefinition(
            name="vowel_ratio",
            description="Compute the ratio of vowels to total characters in a string.",
            parameters=[ToolParam(name="sld", type="str", description="The domain SLD string")],
            returns=ToolReturn(type="float"),
            fn=_vowel_ratio,
            module="m5",
            cost=0.00001,
            cacheable=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="max_consonant_cluster",
            description="Find the longest run of consecutive consonants in a string.",
            parameters=[ToolParam(name="sld", type="str", description="The domain SLD string")],
            returns=ToolReturn(type="int"),
            fn=_max_cluster,
            module="m5",
            cost=0.00001,
            cacheable=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="bigram_frequency",
            description="Compute the average bigram frequency score of a string (0-100).",
            parameters=[ToolParam(name="sld", type="str", description="The domain SLD string")],
            returns=ToolReturn(type="float"),
            fn=_bigram_freq,
            module="m5",
            cost=0.00001,
            cacheable=True,
        )
    )

    # ── M7: Keyword Popularity ──
    registry.register(
        ToolDefinition(
            name="keyword_popularity",
            description="Get search popularity score (0-100) for a term via static adapter.",
            parameters=[ToolParam(name="term", type="str", description="The search term")],
            returns=ToolReturn(type="float"),
            fn=_keyword_score,
            module="m7",
            cost=0.00001,
            cacheable=True,
        )
    )

    # ── M8: CPC ──
    registry.register(
        ToolDefinition(
            name="cpc_lookup",
            description="Look up a word in the CPC keywords map. Returns tier name or None.",
            parameters=[ToolParam(name="word", type="str", description="The word to look up")],
            returns=ToolReturn(type="str", nullable=True),
            fn=_cpc_lookup,
            module="m8",
            cost=0.00001,
            cacheable=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="cpc_tier_rank",
            description="Get numeric rank of a CPC tier (0=elite, 6=none).",
            parameters=[ToolParam(name="tier", type="str", description="CPC tier name")],
            returns=ToolReturn(type="int"),
            fn=_cpc_rank,
            module="m8",
            cost=0.00001,
            cacheable=True,
        )
    )

    # ── M2: TLD ──
    registry.register(
        ToolDefinition(
            name="tld_score",
            description="Get the TLD score (0.2-10.0) for any TLD.",
            parameters=[
                ToolParam(name="tld", type="str", description="TLD without dot, e.g. com"),
            ],
            returns=ToolReturn(type="float"),
            fn=_tld_score,
            module="m2",
            cost=0.00001,
            cacheable=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="tld_tier",
            description="Get the weight profile tier name for a TLD.",
            parameters=[ToolParam(name="tld", type="str", description="The TLD without dot")],
            returns=ToolReturn(type="str"),
            fn=_tld_tier,
            module="m2",
            cost=0.00001,
            cacheable=True,
        )
    )

    # ── M11: Trademark ──
    registry.register(
        ToolDefinition(
            name="known_trademark",
            description="Check if a term is in the curated known trademarks list.",
            parameters=[ToolParam(name="term", type="str", description="The term to check")],
            returns=ToolReturn(type="bool"),
            fn=_known_trademark,
            module="m11",
            cost=0.00001,
            cacheable=True,
        )
    )

    return registry


# ── Tool function implementations ──

_VOWELS = frozenset("aeiou")


def _vowel_ratio(sld: str) -> float:
    v = sum(1 for c in sld if c in _VOWELS)
    return v / len(sld) if sld else 0.0


def _max_cluster(sld: str) -> int:
    max_run = 0
    run = 0
    for c in sld:
        if c not in _VOWELS:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return max_run


def _bigram_freq(sld: str) -> float:
    from ceche.domain.modules.m05_pronounceability import _bigram_score
    return _bigram_score(sld)


def _keyword_score(term: str) -> float:
    import asyncio

    from ceche.infrastructure.keyword.static_adapter import StaticKeywordAdapter
    adapter = StaticKeywordAdapter()
    return asyncio.get_event_loop().run_until_complete(adapter.get_popularity(term))


def _cpc_lookup(word: str) -> str | None:
    import json
    from pathlib import Path
    _root = Path(__file__).resolve().parent.parent.parent.parent
    cpc_file = _root / "domain" / "data" / "cpc_keywords.json"
    with cpc_file.open() as f:
        data: dict[str, str] = json.load(f)
    return data.get(word.lower())


def _cpc_rank(tier: str) -> int:
    order = ["elite", "high", "medium_high", "medium", "low", "informational", "none"]
    try:
        return order.index(tier)
    except ValueError:
        return len(order)


def _tld_score(tld: str) -> float:
    import json
    from pathlib import Path
    _root = Path(__file__).resolve().parent.parent.parent.parent
    tld_file = _root / "domain" / "data" / "tld_scores.json"
    with tld_file.open() as f:
        data: dict[str, float] = json.load(f)
    return float(data.get(tld.lower(), data.get("_default", 0.2)))


def _tld_tier(tld: str) -> str:
    from ceche.domain.modules.m02_tld_table import M2TLDTable
    score = _tld_score(tld)
    return M2TLDTable._resolve_profile(score)


def _known_trademark(term: str) -> bool:
    from ceche.infrastructure.trademark.uspto_adapter import _KNOWN_MARKS
    return term.lower() in _KNOWN_MARKS and _KNOWN_MARKS.get(term.lower()) is not None


_CATALOG: ToolRegistry | None = None


def get_catalog() -> ToolRegistry:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = _build_catalog()
    return _CATALOG
