from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class ModuleStatus(Enum):
    SUCCESS = auto()
    NOT_FOUND = auto()
    QUOTA_EXCEEDED = auto()
    ERROR = auto()
    SKIPPED = auto()


@dataclass(frozen=True)
class RDAPResult:
    registered: bool
    creation_date: datetime.date | None = None
    expiry_date: datetime.date | None = None
    last_changed_date: datetime.date | None = None
    registrar: str | None = None
    domain_name: str | None = None
    statuses: tuple[str, ...] = ()
    raw: dict[str, Any] | None = None

    @property
    def age_years(self) -> float | None:
        if self.creation_date is None:
            return None
        delta = datetime.date.today() - self.creation_date
        return delta.days / 365.25

    def to_dict(self) -> dict[str, Any]:
        return {
            "registered": self.registered,
            "creation_date": str(self.creation_date) if self.creation_date else None,
            "expiry_date": str(self.expiry_date) if self.expiry_date else None,
            "last_changed_date": str(self.last_changed_date) if self.last_changed_date else None,
            "registrar": self.registrar,
            "domain_name": self.domain_name,
            "statuses": list(self.statuses),
            "age_years": self.age_years,
        }


@dataclass(frozen=True)
class SearchResult:
    result_count: int | None
    snippets: list[str]
    competing_tld: bool
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class TrademarkResult:
    conflict: bool
    severity: str
    marks: list[str]
    raw: dict[str, Any] | None = None


class DomainError(Exception):
    """Base exception for domain-layer errors."""


class PortNotConfiguredError(DomainError):
    """Raised when a required port has no adapter wired."""


class ExternalServiceError(DomainError):
    """Raised when an external API call fails."""

    def __init__(self, service: str, message: str, status_code: int | None = None) -> None:
        self.service = service
        self.status_code = status_code
        super().__init__(f"[{service}] {message}")


@dataclass
class ModuleResult:
    value: float | None
    confidence: float
    data: dict[str, Any]
    status: ModuleStatus
    module_name: str = ""

    @staticmethod
    def skipped(name: str) -> ModuleResult:
        return ModuleResult(
            value=None,
            confidence=0.0,
            data={},
            status=ModuleStatus.SKIPPED,
            module_name=name,
        )

    @staticmethod
    def error(name: str, detail: str = "") -> ModuleResult:
        return ModuleResult(
            value=None,
            confidence=0.0,
            data={"error": detail},
            status=ModuleStatus.ERROR,
            module_name=name,
        )
