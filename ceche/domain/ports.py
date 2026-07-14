from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from ceche.domain.models import SearchResult, TrademarkResult


class RDAPPort(ABC):
    @abstractmethod
    async def lookup(self, domain: str) -> dict[str, Any]:
        ...


class ConfigPort(ABC):
    @abstractmethod
    def load(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        ...


class SearchPort(ABC):
    @abstractmethod
    async def search(self, query: str) -> SearchResult:
        ...


class KeywordPopularityPort(ABC):
    @abstractmethod
    async def get_popularity(self, term: str) -> float:
        ...


class TrademarkPort(ABC):
    @abstractmethod
    async def check(self, term: str) -> TrademarkResult:
        ...


class CachePort(ABC):
    @abstractmethod
    async def get(self, key: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        ...

    @abstractmethod
    async def get_or_compute(
        self,
        key: str,
        ttl: int,
        fn: Callable[[], Any],
    ) -> dict[str, Any]:
        ...
