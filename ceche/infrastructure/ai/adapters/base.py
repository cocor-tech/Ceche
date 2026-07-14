from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIResponse:
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class BaseAIAdapter(ABC):
    @abstractmethod
    async def complete(self, prompt: str, system: str = "") -> AIResponse:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    def _compute_cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.cost_per_1k_input + tokens_out * self.cost_per_1k_output) / 1000

    @property
    def cost_per_1k_input(self) -> float:
        return 0.0

    @property
    def cost_per_1k_output(self) -> float:
        return 0.0
