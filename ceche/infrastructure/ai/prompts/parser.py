from __future__ import annotations

import re
from typing import Any

from ceche.infrastructure.ai.prompts.base import OutputFormat


def parse_response(fmt: OutputFormat, raw: str) -> dict[str, Any]:
    raw = raw.strip()
    parsers = {
        OutputFormat.SCORE: _parse_score,
        OutputFormat.TIER: _parse_tier,
        OutputFormat.SINGLE_SPLIT: _parse_single_split,
        OutputFormat.RISK: _parse_risk,
        OutputFormat.LABEL: _parse_label,
        OutputFormat.ASSESSMENT: _parse_assessment,
        OutputFormat.BRAND: _parse_brand,
    }
    parser = parsers.get(fmt, _parse_fallback)
    return parser(raw)


def _parse_score(raw: str) -> dict[str, Any]:
    score_match = re.search(r"SCORE\s*:\s*(\d+(?:\.\d+)?)", raw, re.IGNORECASE)
    conf_match = re.search(r"CONFIDENCE\s*:\s*(0(?:\.\d+)?|1(?:\.0+)?)", raw, re.IGNORECASE)
    cat_match = re.search(r"CATEGORY\s*:\s*(\w+)", raw, re.IGNORECASE)
    return {
        "score": float(score_match.group(1)) if score_match else None,
        "confidence": float(conf_match.group(1)) if conf_match else 0.0,
        "category": cat_match.group(1) if cat_match else None,
    }


def _parse_tier(raw: str) -> dict[str, Any]:
    tier_match = re.search(r"TIER\s*:\s*(\w+)", raw, re.IGNORECASE)
    conf_match = re.search(r"CONFIDENCE\s*:\s*(0(?:\.\d+)?|1(?:\.0+)?)", raw, re.IGNORECASE)
    reason_match = re.search(r"REASON\s*:\s*(.+)", raw, re.IGNORECASE)
    allowed = {"ELITE", "HIGH", "MEDIUM_HIGH", "MEDIUM", "LOW", "INFORMATIONAL", "NONE"}
    tier = (tier_match.group(1) or "").upper() if tier_match else "NONE"
    if tier not in allowed:
        tier = "NONE"
    return {
        "tier": tier.lower(),
        "confidence": float(conf_match.group(1)) if conf_match else 0.0,
        "reason": reason_match.group(1).strip() if reason_match else None,
    }


def _parse_single_split(raw: str) -> dict[str, Any]:
    upper = raw.upper().strip()
    if upper.startswith("SINGLE"):
        return {"decision": "single", "words": None}
    split_match = re.search(r"SPLIT\s*:\s*(.+)", raw, re.IGNORECASE)
    if split_match:
        words = [w.strip().lower() for w in split_match.group(1).split("+") if w.strip()]
        return {"decision": "split", "words": words}
    if "SINGLE" in upper:
        return {"decision": "single", "words": None}
    return {"decision": "unknown", "words": None}


def _parse_risk(raw: str) -> dict[str, Any]:
    risk_match = re.search(r"RISK\s*:\s*(\w+)", raw, re.IGNORECASE)
    conf_match = re.search(r"CONFIDENCE\s*:\s*(0(?:\.\d+)?|1(?:\.0+)?)", raw, re.IGNORECASE)
    note_match = re.search(r"NOTE\s*:\s*(.+)", raw, re.IGNORECASE)
    allowed = {"EXACT", "HIGH", "MEDIUM", "LOW", "NONE"}
    risk = (risk_match.group(1) or "").upper() if risk_match else "NONE"
    if risk not in allowed:
        risk = "NONE"
    return {
        "risk": risk.lower(),
        "confidence": float(conf_match.group(1)) if conf_match else 0.0,
        "note": note_match.group(1).strip() if note_match else None,
    }


def _parse_label(raw: str) -> dict[str, Any]:
    label_match = re.search(r"LABEL\s*:\s*(\w+)", raw, re.IGNORECASE)
    reason_match = re.search(r"REASON\s*:\s*(.+)", raw, re.IGNORECASE)
    allowed = {"HIGH", "MEDIUM", "LOW", "VERY_LOW"}
    label = (label_match.group(1) or "").upper() if label_match else "MEDIUM"
    if label not in allowed:
        label = "MEDIUM"
    return {
        "label": label.lower(),
        "reason": reason_match.group(1).strip() if reason_match else None,
    }


def _parse_assessment(raw: str) -> dict[str, Any]:
    assess_match = re.search(r"ASSESSMENT\s*:\s*(\w+)", raw, re.IGNORECASE)
    adjust_match = re.search(r"ADJUSTED\s*:\s*(\d+(?:\.\d+)?)", raw, re.IGNORECASE)
    reason_match = re.search(r"REASON\s*:\s*(.+)", raw, re.IGNORECASE)
    return {
        "assessment": (assess_match.group(1) or "").lower() if assess_match else "reasonable",
        "adjusted": float(adjust_match.group(1)) if adjust_match else None,
        "reason": reason_match.group(1).strip() if reason_match else None,
    }


def _parse_brand(raw: str) -> dict[str, Any]:
    score_match = re.search(r"SCORE\s*:\s*(\d+(?:\.\d+)?)", raw, re.IGNORECASE)
    conf_match = re.search(r"CONFIDENCE\s*:\s*(0(?:\.\d+)?|1(?:\.0+)?)", raw, re.IGNORECASE)
    industry_match = re.search(r"INDUSTRY\s*:\s*(\w+)", raw, re.IGNORECASE)
    return {
        "score": float(score_match.group(1)) if score_match else None,
        "confidence": float(conf_match.group(1)) if conf_match else 0.0,
        "industry": industry_match.group(1) if industry_match else None,
    }


def _parse_fallback(raw: str) -> dict[str, Any]:
    return {"raw": raw}
