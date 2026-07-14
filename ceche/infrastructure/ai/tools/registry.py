from __future__ import annotations

from typing import Any

from ceche.infrastructure.ai.tools.definition import ToolDefinition
from ceche.infrastructure.ai.tools.sandbox import ExecutionSandbox, ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"tool '{name}' not registered")
        return self._tools[name]

    def list_for_module(self, module: str) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.module == module]

    def generate_openai_schema(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> ToolResult:
        tool = self.get(name)
        return await ExecutionSandbox.execute(tool, params)

    def tool_names(self) -> list[str]:
        return sorted(self._tools.keys())

    def module_names(self) -> list[str]:
        return sorted({t.module for t in self._tools.values()})
