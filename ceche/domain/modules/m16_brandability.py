from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.ai_refine import ai_refine_module
from ceche.domain.modules.base import BaseModule
from ceche.domain.ports import AIPort

_VOWELS = frozenset("aeiou")

_STRONG_ENDS = frozenset({
    "ify", "ly", "ex", "io", "ox", "ix", "ux", "oo", "ee",
    "ia", "elle", "ora", "ina", "ara", "ica", "ota", "ula", "ena",
    "oa", "ay", "ey", "oy", "in", "en", "al", "el", "il", "ol", "ul",
    "va", "vi", "vo", "vu", "ka", "ke", "ki", "ko", "ku",
    "ba", "be", "bi", "bo", "bu", "da", "de", "di", "do", "du",
    "fa", "fe", "fi", "fo", "mi", "na", "ne", "ni", "no", "nu",
    "pa", "pe", "pi", "po", "pu", "ta", "te", "ti", "to", "tu",
    "za", "ze", "zi", "zo",
})

_MULT_MAP: list[tuple[float, float]] = [
    (80.0, 8.0),
    (60.0, 5.0),
    (40.0, 3.0),
    (20.0, 2.0),
    (0.0, 1.0),
]

_IDEAL_MIN_LEN = 4
_IDEAL_MAX_LEN = 7


class M16Brandability(BaseModule):
    name = "m16_brandability"

    def __init__(self, ai: AIPort | None = None) -> None:
        self._ai = ai

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        sld: str | None = context.get("sld")
        if not sld:
            return ModuleResult.error(self.name, "no sld in context")

        m6_status = context.get("m6_status")
        if m6_status and m6_status == "split_found":
            return ModuleResult(
                module_name=self.name,
                value=None,
                confidence=0.0,
                data={"reason": "M6 found a split — brandability not applicable"},
                status=ModuleStatus.SKIPPED,
            )

        sld_lower = sld.lower()
        length = len(sld_lower)

        has_vowel = any(c in _VOWELS for c in sld_lower)

        syllable_score = _syllable_flow(sld_lower)
        pattern_score = _pattern_score(sld_lower)
        length_score = _length_score(length)

        score = syllable_score * 0.4 + pattern_score * 0.3 + length_score * 0.3
        score = max(0.0, min(100.0, score))

        if not has_vowel:
            score = min(score, 15.0)
        multiplier = _resolve_multiplier(score)

        if self._ai and score < 80:
            prompt = (
                f"String: {sld_lower}\n"
                f"Length: {length}\n"
                f"Current brandability score: {score:.0f}/100\n\n"
                f"Rate as a brand name (0-100). "
                f"Respond ONLY with: SCORE:X"
            )
            raw = await ai_refine_module(self._ai, self.name, context, prompt)
            if raw:
                import re
                m = re.search(r"SCORE\s*:\s*(\d+(?:\.\d+)?)", raw, re.IGNORECASE)
                if m:
                    ai_score = float(m.group(1))
                    score = score * 0.4 + ai_score * 0.6
                    multiplier = _resolve_multiplier(score)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=min(1.0, score / 100.0),
            data={
                "score": round(score, 2),
                "multiplier": multiplier,
                "syllable_score": round(syllable_score, 2),
                "pattern_score": round(pattern_score, 2),
                "length_score": round(length_score, 2),
            },
            status=ModuleStatus.SUCCESS,
        )


def _syllable_flow(s: str) -> float:
    runs = 0
    in_vowel = False
    for c in s:
        is_vowel = c in _VOWELS
        if is_vowel and not in_vowel:
            runs += 1
        in_vowel = is_vowel

    if runs == 0:
        return 0.0
    if runs == 1:
        return 40.0
    if runs == 2:
        return 100.0
    if runs == 3:
        return 90.0
    if runs == 4:
        return 60.0
    if runs == 5:
        return 30.0
    return max(5.0, 10.0 - (runs - 5) * 2.0)


def _pattern_score(s: str) -> float:
    score = 0.0
    for pattern in _STRONG_ENDS:
        if s.endswith(pattern):
            score += 20.0
            break

    cvc_count = 0
    for i in range(len(s) - 2):
        if s[i] not in _VOWELS and s[i + 1] in _VOWELS and s[i + 2] not in _VOWELS:
            cvc_count += 1
    score += min(30.0, cvc_count * 10.0)

    doubles = sum(1 for i in range(len(s) - 1) if s[i] == s[i + 1])
    score += min(15.0, doubles * 5.0)

    return min(100.0, score + 35.0)


def _length_score(length: int) -> float:
    if length <= 1:
        return 20.0
    if length == 2:
        return 40.0
    if length == 3:
        return 60.0
    if _IDEAL_MIN_LEN <= length <= _IDEAL_MAX_LEN:
        return 100.0
    extra = length - _IDEAL_MAX_LEN
    return max(10.0, 100.0 - extra * 12.0)


def _resolve_multiplier(score: float) -> float:
    for threshold, mult in _MULT_MAP:
        if score >= threshold:
            return mult
    return 1.0
