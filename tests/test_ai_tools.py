"""Tests for Layer 2 — Tool Registry."""

from __future__ import annotations

import pytest

from ceche.infrastructure.ai.tools.catalog import get_catalog
from ceche.infrastructure.ai.tools.definition import ToolDefinition, ToolParam, ToolReturn
from ceche.infrastructure.ai.tools.registry import ToolRegistry
from ceche.infrastructure.ai.tools.sandbox import ExecutionSandbox, ToolExecutionError


class TestToolDefinition:
    def test_param_names(self):
        td = ToolDefinition(
            name="test",
            description="test tool",
            parameters=[
                ToolParam(name="a", type="str", required=True),
                ToolParam(name="b", type="int", required=False),
            ],
            returns=ToolReturn(type="str"),
        )
        assert td.param_names() == ["a"]

    def test_openai_schema(self):
        td = ToolDefinition(
            name="cpc_lookup",
            description="Look up a word in the CPC keywords map",
            parameters=[ToolParam(name="word", type="str", description="The word")],
            returns=ToolReturn(type="str", nullable=True),
        )
        schema = td.to_openai_schema()
        assert schema["name"] == "cpc_lookup"
        assert "word" in schema["parameters"]["properties"]
        assert schema["parameters"]["type"] == "object"


class TestRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        td = ToolDefinition(
            name="test", description="d",
            parameters=[ToolParam(name="x", type="int")],
            returns=ToolReturn(type="int"),
        )
        reg.register(td)
        assert reg.get("test") is td

    def test_get_unknown_raises(self):
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.get("nonexistent")

    def test_list_for_module(self):
        reg = ToolRegistry()
        reg.register(
            ToolDefinition(name="a", description="", module="m6",
                           parameters=[], returns=ToolReturn(type="int")))
        reg.register(
            ToolDefinition(name="b", description="", module="m7",
                           parameters=[], returns=ToolReturn(type="int")))
        m6_tools = reg.list_for_module("m6")
        assert len(m6_tools) == 1
        assert m6_tools[0].name == "a"

    def test_generate_openai_schema(self):
        reg = ToolRegistry()
        reg.register(
            ToolDefinition(name="test", description="d",
                           parameters=[ToolParam(name="word", type="str")],
                           returns=ToolReturn(type="str")))
        schemas = reg.generate_openai_schema()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "test"

    async def test_execute(self):
        reg = ToolRegistry()
        reg.register(
            ToolDefinition(
                name="double", description="doubles input",
                parameters=[ToolParam(name="x", type="int")],
                returns=ToolReturn(type="int"),
                fn=lambda x: x * 2,
            ))
        result = await reg.execute("double", {"x": 5})
        assert result.value == 10


class TestSandbox:
    async def test_timeout(self):
        async def slow():
            import asyncio
            await asyncio.sleep(10)
            return 1

        td = ToolDefinition(
            name="slow", description="", parameters=[],
            returns=ToolReturn(type="int"), fn=slow,
        )
        with pytest.raises(ToolExecutionError, match="timed out"):
            await ExecutionSandbox.execute(td, {})

    async def test_injection_blocked(self):
        td = ToolDefinition(
            name="echo", description="",
            parameters=[ToolParam(name="x", type="str")],
            returns=ToolReturn(type="str"), fn=lambda x: x,
        )
        with pytest.raises(ToolExecutionError, match="unsafe"):
            await ExecutionSandbox.execute(td, {"x": "ls;rm"})

    async def test_missing_param(self):
        td = ToolDefinition(
            name="need_x", description="",
            parameters=[ToolParam(name="x", type="str", required=True)],
            returns=ToolReturn(type="str"), fn=lambda x: x,
        )
        with pytest.raises(ToolExecutionError, match="missing"):
            await ExecutionSandbox.execute(td, {})


class TestCatalog:
    def test_catalog_loaded(self):
        cat = get_catalog()
        names = cat.tool_names()
        assert "word_frequency" in names
        assert "valid_word" in names
        assert "vowel_ratio" in names
        assert "cpc_lookup" in names
        assert "cpc_tier_rank" in names
        assert "tld_score" in names
        assert "tld_tier" in names
        assert "keyword_popularity" in names
        assert "known_trademark" in names
        assert "max_consonant_cluster" in names
        assert "bigram_frequency" in names

    def test_modules_populated(self):
        cat = get_catalog()
        mods = cat.module_names()
        assert "m5" in mods
        assert "m6" in mods
        assert "m7" in mods
        assert "m8" in mods
        assert "m2" in mods

    def test_openai_schema_generation(self):
        cat = get_catalog()
        schemas = cat.generate_openai_schema()
        assert len(schemas) >= 10

    async def test_cpc_lookup_tool(self):
        cat = get_catalog()
        result = await cat.execute("cpc_lookup", {"word": "insurance"})
        assert result.value is not None
        assert result.value == "elite"

    async def test_cpc_lookup_missing(self):
        cat = get_catalog()
        result = await cat.execute("cpc_lookup", {"word": "xyzzy123"})
        assert result.value is None

    async def test_tld_score_tool(self):
        cat = get_catalog()
        result = await cat.execute("tld_score", {"tld": "com"})
        assert result.value == 10.0

    async def test_tld_score_unknown(self):
        cat = get_catalog()
        result = await cat.execute("tld_score", {"tld": "nonexistent"})
        assert result.value == 0.2

    async def test_word_frequency_tool(self):
        cat = get_catalog()
        result = await cat.execute("word_frequency", {"word": "car"})
        assert result.value is not None
        assert result.value > 0

    async def test_valid_word_tool(self):
        cat = get_catalog()
        result = await cat.execute("valid_word", {"word": "car"})
        assert result.value is True

    async def test_known_trademark_tool(self):
        cat = get_catalog()
        result = await cat.execute("known_trademark", {"term": "google"})
        assert result.value is True

    async def test_vowel_ratio_tool(self):
        cat = get_catalog()
        result = await cat.execute("vowel_ratio", {"sld": "aeiou"})
        assert result.value > 0.5

    async def test_max_consonant_cluster(self):
        cat = get_catalog()
        result = await cat.execute("max_consonant_cluster", {"sld": "bcdfgh"})
        assert result.value == 6

    async def test_cpc_tier_rank_tool(self):
        cat = get_catalog()
        result = await cat.execute("cpc_tier_rank", {"tier": "elite"})
        assert result.value == 0

    async def test_tld_tier_tool(self):
        cat = get_catalog()
        result = await cat.execute("tld_tier", {"tld": "com"})
        assert result.value == "tier_10"

    async def test_bigram_frequency_tool(self):
        cat = get_catalog()
        result = await cat.execute("bigram_frequency", {"sld": "car"})
        assert result.value is not None
        assert 0 <= result.value <= 100
