from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from ceche.infrastructure.ai.tools.definition import ToolDefinition


class ToolExecutionError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ExecutionSandbox:
    TIMEOUT = 5.0

    _INJECTION_PATTERN = re.compile(r"[;&|`$(){}\[\]]")

    @classmethod
    async def execute(
        cls,
        tool: ToolDefinition,
        params: dict[str, Any],
    ) -> ToolResult:
        cls._validate_params(tool, params)
        sanitized = cls._sanitize(params)
        try:
            raw = await asyncio.wait_for(
                _run(tool, sanitized), timeout=cls.TIMEOUT,
            )
            cls._validate_return(tool, raw)
            return ToolResult(value=raw)
        except asyncio.TimeoutError:
            raise ToolExecutionError(
                f"tool {tool.name} timed out after {cls.TIMEOUT}s"
            ) from None
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"tool {tool.name} failed: {exc}") from exc

    @classmethod
    def _validate_params(cls, tool: ToolDefinition, params: dict[str, Any]) -> None:
        for p in tool.parameters:
            if p.required and p.name not in params:
                raise ToolExecutionError(
                    f"missing required param '{p.name}' for tool '{tool.name}'",
                )
        for key in params:
            if key not in {p.name for p in tool.parameters}:
                raise ToolExecutionError(
                    f"unknown param '{key}' for tool '{tool.name}'",
                )

    @classmethod
    def _sanitize(cls, params: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in params.items():
            if isinstance(value, str):
                value = value.strip().lower()
                if cls._INJECTION_PATTERN.search(value):
                    raise ToolExecutionError(f"potentially unsafe value for param '{key}'")
            result[key] = value
        return result

    @classmethod
    def _validate_return(
        cls, tool: ToolDefinition, raw: Any,
    ) -> None:
        if raw is None and not tool.returns.nullable:
            raise ToolExecutionError(f"tool '{tool.name}' returned None unexpectedly")
        if raw is not None and tool.returns.type != "any":
            expected = tool.returns.type
            if ((expected == "int" and isinstance(raw, (int, float)))
                    or (expected == "float" and isinstance(raw, (int, float)))
                    or (expected == "list" and isinstance(raw, list))):
                return
            if expected == "str" and isinstance(raw, str):
                return
            if expected == "dict" and isinstance(raw, dict):
                return
            if expected == "bool" and isinstance(raw, bool):
                return


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return "any"


async def _run(tool: ToolDefinition, params: dict[str, Any]) -> Any:
    if tool.fn is None:
        return None
    result = tool.fn(**params)
    if asyncio.iscoroutine(result):
        return await result
    return result


@dataclass
class ToolResult:
    value: Any
    error: str | None = None
