from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OutputFormat(Enum):
    SCORE = "SCORE"
    TIER = "TIER"
    SINGLE_SPLIT = "SINGLE_SPLIT"
    RISK = "RISK"
    LABEL = "LABEL"
    ASSESSMENT = "ASSESSMENT"
    BRAND = "BRAND"


@dataclass
class PromptExample:
    input: str
    output: str
    explanation: str = ""


@dataclass
class Prompt:
    id: str
    version: str
    module: str
    purpose: str
    system: str
    user_template: str
    examples: list[PromptExample] = field(default_factory=list)
    output_format: OutputFormat = OutputFormat.SCORE
    tools_allowed: list[str] = field(default_factory=list)
    max_tokens: int = 150
    temperature: float = 0.1

    def render(self, **kwargs: str) -> str:
        return self.user_template.format(**kwargs)
