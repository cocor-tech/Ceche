from __future__ import annotations

import math
from typing import Any

from wordfreq import word_frequency

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule

_MIN_FREQ = 1e-7
_MIN_FREQ_SHORT = 1e-5
_MIN_WORD_LEN = 2
_SPLIT_PENALTY = 5.0


class M6Segmenter(BaseModule):
    name = "m6_segmenter"

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        sld: str | None = context.get("sld")
        if not sld:
            return ModuleResult.error(self.name, "no sld in context")

        sld_lower = sld.lower()

        words = _segment(sld_lower)

        if words is None:
            return ModuleResult(
                module_name=self.name,
                value=None,
                confidence=0.0,
                data={
                    "winner": None,
                    "word_count": None,
                    "confidence": 0.0,
                    "status": "no_split",
                },
                status=ModuleStatus.SKIPPED,
            )

        word_count = len(words)
        confidence = _compute_confidence(words)

        return ModuleResult(
            module_name=self.name,
            value=None,
            confidence=confidence,
            data={
                "winner": words,
                "word_count": word_count,
                "confidence": round(confidence, 2),
                "status": "split_found",
            },
            status=ModuleStatus.SUCCESS,
        )


def _segment(s: str) -> list[str] | None:
    n = len(s)
    _freq_cache: dict[str, float] = {}

    def _freq(word: str) -> float:
        if word not in _freq_cache:
            f = word_frequency(word, "en")
            _freq_cache[word] = f if f > 0 else 0.0
        return _freq_cache[word]

    def _valid(word: str) -> bool:
        if len(word) < _MIN_WORD_LEN:
            return False
        f = _freq(word)
        if f <= 0:
            return False
        threshold = _MIN_FREQ_SHORT if len(word) == 2 else _MIN_FREQ
        return f >= threshold

    dp_score = [-math.inf] * (n + 1)
    dp_prev = [-1] * (n + 1)
    dp_score[0] = 0.0

    for i in range(1, n + 1):
        for j in range(i):
            word = s[j:i]
            if _valid(word):
                freq = _freq(word)
                split_cost = _SPLIT_PENALTY if j > 0 else 0.0
                score = dp_score[j] + math.log(freq) - split_cost
                if score > dp_score[i]:
                    dp_score[i] = score
                    dp_prev[i] = j

    if dp_score[n] <= -math.inf:
        return None

    words: list[str] = []
    i = n
    while i > 0:
        prev = dp_prev[i]
        words.append(s[prev:i])
        i = prev
    words.reverse()
    return words


def _compute_confidence(words: list[str]) -> float:
    if not words:
        return 0.0
    freqs = [word_frequency(w, "en") for w in words]
    freqs = [max(f, _MIN_FREQ) for f in freqs]
    log_mean = sum(math.log(f) for f in freqs) / len(freqs)
    if log_mean >= math.log(1e-4):
        return 1.0
    if log_mean >= math.log(1e-5):
        return 0.8
    if log_mean >= math.log(1e-6):
        return 0.6
    if log_mean >= math.log(_MIN_FREQ):
        return 0.4
    return 0.2
