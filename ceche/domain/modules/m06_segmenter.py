from __future__ import annotations

import math
from typing import Any

from wordfreq import word_frequency

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule
from ceche.domain.ports import AIPort

_MIN_FREQ = 1e-5
_MIN_WORD_LEN = 2
_SPLIT_PENALTY = 5.0
_SINGLE_CHAR_WORDS = frozenset({"a", "i"})


class M6Segmenter(BaseModule):
    name = "m6_segmenter"

    def __init__(self, ai: AIPort | None = None) -> None:
        self._ai = ai

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        sld: str | None = context.get("sld")
        if not sld:
            return ModuleResult.error(self.name, "no sld in context")

        sld_lower = sld.lower()
        words = _segment(sld_lower)

        if words and len(words) >= 3 and self._ai:
            words = await self._ai_disambiguate(sld_lower, words)

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

    async def _ai_disambiguate(self, sld: str, dp_words: list[str]) -> list[str] | None:
        if not self._ai:
            return dp_words
        joined = "+".join(dp_words)
        prompt = (
            f"Is '{sld}' better treated as a single brandable word or split into '{joined}'?\n"
            f"Reply SINGLE if it should stay whole.\n"
            f"Reply SPLIT: followed by the correct split words separated by + if it's real words.\n"
            f"Example: 'topinsurance' → SPLIT:top+insurance\n"
            f"Example: 'gojominitia' → SINGLE\n"
            f"Only reply with SINGLE or SPLIT:word1+word2."
        )
        try:
            result = await self._ai.complete(prompt)
            if not result:
                return dp_words
            result = result.strip().upper()
            if result.startswith("SINGLE"):
                return None
            if result.startswith("SPLIT:"):
                parts = result[6:].strip().lower().split("+")
                if all(len(p) >= 2 for p in parts):
                    return parts
        except Exception:
            pass
        return dp_words


def _segment(s: str) -> list[str] | None:
    n = len(s)
    _freq_cache: dict[str, float] = {}

    def _freq(word: str) -> float:
        if word not in _freq_cache:
            f = word_frequency(word, "en")
            _freq_cache[word] = f if f > 0 else 0.0
        return _freq_cache[word]

    def _valid(word: str) -> bool:
        if len(word) < _MIN_WORD_LEN and word not in _SINGLE_CHAR_WORDS:
            return False
        f = _freq(word)
        if f <= 0:
            return False
        return f >= _MIN_FREQ

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
