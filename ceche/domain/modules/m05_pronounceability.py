from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule

_VOWELS = frozenset("aeiou")

_BIGRAM_FREQ: dict[str, float] = {
    "th": 1.0, "he": 0.94, "in": 0.88, "er": 0.85, "an": 0.82,
    "on": 0.78, "at": 0.76, "en": 0.74, "nd": 0.72, "ti": 0.70,
    "es": 0.68, "or": 0.66, "te": 0.64, "of": 0.62, "ed": 0.60,
    "is": 0.58, "it": 0.56, "al": 0.54, "ar": 0.52, "st": 0.50,
    "to": 0.48, "nt": 0.46, "ng": 0.44, "se": 0.42, "ha": 0.40,
    "as": 0.39, "ou": 0.38, "io": 0.37, "le": 0.36, "ve": 0.35,
    "co": 0.34, "me": 0.33, "de": 0.32, "hi": 0.31, "ri": 0.30,
    "ro": 0.29, "ic": 0.28, "ne": 0.27, "ea": 0.26, "ra": 0.25,
    "ce": 0.24, "li": 0.23, "ch": 0.22, "ll": 0.21, "be": 0.20,
    "ma": 0.19, "si": 0.18, "om": 0.17, "ur": 0.16, "ac": 0.15,
    "et": 0.14, "ta": 0.14, "pe": 0.14, "di": 0.14, "el": 0.14,
    "bl": 0.13, "tr": 0.13, "pr": 0.13, "gr": 0.13, "pl": 0.13,
    "br": 0.12, "cr": 0.12, "dr": 0.12, "fr": 0.12, "gl": 0.12,
    "sc": 0.10, "sm": 0.10, "sn": 0.10, "sp": 0.10, "sw": 0.10,
    "gh": 0.10, "ph": 0.10, "qu": 0.10, "sh": 0.10, "wh": 0.10,
    "wr": 0.10, "ck": 0.10, "lo": 0.10, "mo": 0.10, "no": 0.10,
    "po": 0.10, "so": 0.10, "tu": 0.10, "tw": 0.10, "wo": 0.10,
    "ab": 0.10, "ad": 0.10, "ag": 0.10, "am": 0.10, "ap": 0.10,
    "bo": 0.10, "bu": 0.10, "ca": 0.10, "ci": 0.10, "cu": 0.10,
    "do": 0.10, "du": 0.10, "ec": 0.10, "eg": 0.10, "em": 0.10,
    "ep": 0.10, "ev": 0.10, "ex": 0.10, "fa": 0.10, "fe": 0.10,
    "fi": 0.10, "fo": 0.10, "fu": 0.10, "ga": 0.10, "ge": 0.10,
    "gi": 0.10, "go": 0.10, "gu": 0.10, "ho": 0.10, "hu": 0.10,
    "la": 0.10, "lu": 0.10, "mi": 0.10, "mu": 0.10, "na": 0.10,
    "ni": 0.10, "nu": 0.10, "oc": 0.10, "ol": 0.10, "op": 0.10,
    "ov": 0.10, "ow": 0.10, "pa": 0.10, "pi": 0.10, "pu": 0.10,
    "re": 0.10, "ru": 0.10, "sa": 0.10, "su": 0.10,
    "ul": 0.10, "un": 0.10, "us": 0.10, "ut": 0.10, "vi": 0.10,
    "wa": 0.10, "we": 0.10, "wi": 0.10, "xa": 0.10, "ye": 0.10,
    "yo": 0.10, "za": 0.10, "ze": 0.10, "zi": 0.10, "zo": 0.10,
}

_BIGRAM_DEFAULT = 0.05

_MULT_MAP: list[tuple[float, float]] = [
    (90.0, 2.0),
    (70.0, 1.5),
    (40.0, 1.2),
    (0.0, 1.0),
]


class M5Pronounceability(BaseModule):
    name = "m5_pronounceability"

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        sld: str | None = context.get("sld")
        if not sld:
            return ModuleResult.error(self.name, "no sld in context")

        sld_lower = sld.lower()
        length = len(sld_lower)

        if length <= 2:
            return ModuleResult(
                module_name=self.name,
                value=2.0,
                confidence=1.0,
                data={
                    "score": 100.0,
                    "multiplier": 2.0,
                    "length": length,
                    "reason": "too short to be unpronounceable",
                },
                status=ModuleStatus.SUCCESS,
            )

        vowel_score = _vowel_score(sld_lower)
        cluster_score = _cluster_score(sld_lower)
        bigram_score = _bigram_score(sld_lower)

        score = vowel_score * 0.4 + cluster_score * 0.3 + bigram_score * 0.3
        score = max(0.0, min(100.0, score))
        multiplier = _resolve_multiplier(score)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=1.0,
            data={
                "score": round(score, 2),
                "multiplier": multiplier,
                "vowel_score": round(vowel_score, 2),
                "cluster_score": round(cluster_score, 2),
                "bigram_score": round(bigram_score, 2),
            },
            status=ModuleStatus.SUCCESS,
        )


def _vowel_ratio(s: str) -> float:
    vowel_count = sum(1 for c in s if c in _VOWELS)
    return vowel_count / len(s) if s else 0.0


def _vowel_score(s: str) -> float:
    ratio = _vowel_ratio(s)
    if ratio > 0.80:
        return 10.0
    dev = abs(ratio - 0.40)
    score = 100.0 * (1.0 - dev / 0.40)
    return max(0.0, min(100.0, score))


def _cluster_score(s: str) -> float:
    max_run = 0
    run = 0
    for c in s:
        if c not in _VOWELS and c != "-":
            run += 1
        else:
            run = 0
        max_run = max(max_run, run)

    if max_run <= 2:
        return 100.0
    if max_run == 3:
        return 70.0
    if max_run == 4:
        return 30.0
    return max(0.0, 10.0 - (max_run - 4) * 3.0)


def _bigram_score(s: str) -> float:
    pairs = [s[i : i + 2] for i in range(len(s) - 1)]
    if not pairs:
        return _BIGRAM_DEFAULT * 100

    freqs = [_BIGRAM_FREQ.get(p, _BIGRAM_DEFAULT) for p in pairs]
    avg = sum(freqs) / len(freqs)
    return avg * 100.0


def _resolve_multiplier(score: float) -> float:
    for threshold, mult in _MULT_MAP:
        if score >= threshold:
            return mult
    return 1.0
