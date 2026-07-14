from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParam:
    name: str
    type: str
    required: bool = True
    description: str = ""
    enum: list[str] | None = None


@dataclass
class ToolReturn:
    type: str
    description: str = ""
    nullable: bool = False


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: list[ToolParam] = field(default_factory=list)
    returns: ToolReturn = field(default_factory=lambda: ToolReturn(type="any"))
    fn: Callable[..., Any] | None = None
    module: str = ""
    cost: float = 0.0
    cacheable: bool = False

    def param_names(self) -> list[str]:
        return [p.name for p in self.parameters if p.required]

    def to_openai_schema(self) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for p in self.parameters:
            prop: dict[str, Any] = {
                "type": _to_json_type(p.type),
                "description": p.description,
            }
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


def _to_json_type(t: str) -> str:
    mapping: dict[str, str] = {
        "str": "string", "int": "integer", "float": "number",
        "bool": "boolean", "list": "array", "dict": "object",
    }
    return mapping.get(t, "string")
