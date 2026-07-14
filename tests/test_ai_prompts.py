"""Tests for Layer 3 — Prompt Catalog."""

from __future__ import annotations

from ceche.infrastructure.ai.prompts.base import OutputFormat, Prompt, PromptExample
from ceche.infrastructure.ai.prompts.catalog import get_prompt, list_prompts
from ceche.infrastructure.ai.prompts.parser import parse_response


class TestPromptBase:
    def test_render(self):
        p = Prompt(
            id="test", version="1.0.0", module="m5", purpose="test",
            system="sys", user_template="Hello {name}",
            output_format=OutputFormat.SCORE,
        )
        result = p.render(name="world")
        assert result == "Hello world"

    def test_examples_attached(self):
        p = Prompt(
            id="test", version="1.0.0", module="m6", purpose="test",
            system="s", user_template="{x}",
            examples=[PromptExample(input="a", output="b")],
            output_format=OutputFormat.SINGLE_SPLIT,
        )
        assert len(p.examples) == 1
        assert p.examples[0].input == "a"

    def test_tools_allowed(self):
        p = Prompt(
            id="t", version="1", module="m6", purpose="",
            system="", user_template="{x}",
            tools_allowed=["word_frequency", "valid_word"],
            output_format=OutputFormat.SINGLE_SPLIT,
        )
        assert "word_frequency" in p.tools_allowed


class TestParser:
    def test_parse_score(self):
        result = parse_response(OutputFormat.SCORE, "SCORE:95 CONFIDENCE:0.95 CATEGORY:VERY_HIGH")
        assert result["score"] == 95.0
        assert result["confidence"] == 0.95
        assert result["category"] == "VERY_HIGH"

    def test_parse_score_extra_text(self):
        result = parse_response(OutputFormat.SCORE, "some extra text SCORE:42 more text CONFIDENCE:0.8 end")
        assert result["score"] == 42.0
        assert result["confidence"] == 0.8

    def test_parse_score_missing_fields(self):
        result = parse_response(OutputFormat.SCORE, "blah blah")
        assert result["score"] is None
        assert result["confidence"] == 0.0
        assert result["category"] is None

    def test_parse_tier(self):
        result = parse_response(OutputFormat.TIER, "TIER:ELITE CONFIDENCE:0.95 REASON:Legal term with high value")
        assert result["tier"] == "elite"
        assert result["confidence"] == 0.95
        assert "legal term" in (result["reason"] or "").lower()

    def test_parse_tier_invalid_allowlist(self):
        result = parse_response(OutputFormat.TIER, "TIER:SUPER_ELITE CONFIDENCE:0.9")
        assert result["tier"] == "none"

    def test_parse_single(self):
        result = parse_response(OutputFormat.SINGLE_SPLIT, "SINGLE")
        assert result["decision"] == "single"
        assert result["words"] is None

    def test_parse_split(self):
        result = parse_response(OutputFormat.SINGLE_SPLIT, "SPLIT:top+insurance")
        assert result["decision"] == "split"
        assert result["words"] == ["top", "insurance"]

    def test_parse_split_case_insensitive(self):
        result = parse_response(OutputFormat.SINGLE_SPLIT, "split:Best+Car")
        assert result["decision"] == "split"
        assert result["words"] == ["best", "car"]

    def test_parse_risk(self):
        result = parse_response(OutputFormat.RISK, "RISK:HIGH CONFIDENCE:0.95 NOTE:clear infringement")
        assert result["risk"] == "high"
        assert result["confidence"] == 0.95
        assert "infringement" in (result["note"] or "")

    def test_parse_risk_invalid(self):
        result = parse_response(OutputFormat.RISK, "RISK:WILDCARD")
        assert result["risk"] == "none"

    def test_parse_label(self):
        result = parse_response(OutputFormat.LABEL, "LABEL:HIGH REASON:Most modules returned data")
        assert result["label"] == "high"

    def test_parse_label_invalid(self):
        result = parse_response(OutputFormat.LABEL, "LABEL:SUPER_HIGH")
        assert result["label"] == "medium"

    def test_parse_assessment(self):
        result = parse_response(OutputFormat.ASSESSMENT, "ASSESSMENT:overvalued ADJUSTED:5000 REASON:Market comps suggest lower")
        assert result["assessment"] == "overvalued"
        assert result["adjusted"] == 5000.0

    def test_parse_brand(self):
        result = parse_response(OutputFormat.BRAND, "SCORE:78 CONFIDENCE:0.8 INDUSTRY:tech")
        assert result["score"] == 78.0
        assert result["confidence"] == 0.8
        assert result["industry"] == "tech"


class TestCatalog:
    def test_all_prompts_registered(self):
        names = list_prompts()
        assert "m05_pronounce" in names
        assert "m06_disambiguate" in names
        assert "m06_verify_nosplit" in names
        assert "m07_keyword" in names
        assert "m08_cpc" in names
        assert "m11_trademark" in names
        assert "m13_confidence" in names
        assert "m15_pricing" in names
        assert "m16_brandability" in names

    def test_get_prompt_valid(self):
        p = get_prompt("m06_disambiguate")
        assert p is not None
        assert p.module == "m6"
        assert p.version == "1.0.0"

    def test_get_prompt_missing(self):
        assert get_prompt("nonexistent") is None

    def test_prompts_have_examples(self):
        for pid in list_prompts():
            p = get_prompt(pid)
            assert p is not None
            assert len(p.examples) >= 1, f"{pid} has no examples"

    def test_m06_prompts_have_tools(self):
        p = get_prompt("m06_disambiguate")
        assert p is not None
        assert len(p.tools_allowed) >= 1

    def test_m16_temperature(self):
        p = get_prompt("m16_brandability")
        assert p is not None
        assert p.temperature == 0.3

    def test_classification_prompts_low_temp(self):
        for pid in ("m08_cpc", "m11_trademark", "m05_pronounce"):
            p = get_prompt(pid)
            assert p is not None
            assert p.temperature <= 0.1, f"{pid} temperature should be <= 0.1"
