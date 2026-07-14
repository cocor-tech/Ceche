from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ceche.domain.models import ModuleResult


class BaseModule(ABC):
    name: str = ""

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> ModuleResult:
        ...
