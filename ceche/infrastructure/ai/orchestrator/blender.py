from __future__ import annotations

from typing import Any


def blend_result(
    original_value: float | None,
    original_confidence: float,
    ai_value: float | None,
    ai_confidence: float,
    original_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    weight = max(0.1, min(0.9, 1.0 - original_confidence))

    if original_confidence >= 0.9:
        weight = min(weight, 0.5)

    if ai_value is not None and original_value is not None:
        blended = original_value * (1 - weight) + ai_value * weight
    elif ai_value is not None:
        blended = ai_value
    elif original_value is not None:
        blended = original_value
    else:
        blended = None

    new_confidence = min(1.0, original_confidence + ai_confidence * weight)

    return {
        "value": blended,
        "confidence": new_confidence,
        "blend_weight": round(weight, 3),
        "source": _source_label(weight),
        "original_value": original_value,
        "original_confidence": original_confidence,
        "ai_value": ai_value,
        "ai_confidence": ai_confidence,
    }


def _source_label(weight: float) -> str:
    if weight > 0.6:
        return "ai_refined"
    if weight < 0.3:
        return "deterministic"
    return "blended"
