from __future__ import annotations

import datetime
from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus, RDAPResult
from ceche.domain.modules.base import BaseModule
from ceche.domain.ports import CachePort, RDAPPort

_AGE_20_PLUS = 20
_AGE_10_PLUS = 10
_AGE_5_PLUS = 5
_AGE_1_PLUS = 1

_MULT_20_PLUS = 3.0
_MULT_10_PLUS = 2.0
_MULT_5_PLUS = 1.5
_MULT_1_PLUS = 1.2
_MULT_DEFAULT = 1.0


class M1RDAP(BaseModule):
    name = "m1_rdap"

    RDAP_CACHE_TTL = 86400

    def __init__(self, rdap: RDAPPort, cache: CachePort) -> None:
        self._rdap = rdap
        self._cache = cache

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        domain: str | None = context.get("domain_name")
        if not domain:
            return ModuleResult.error(self.name, "no domain in context")
        try:
            raw = await self._cache.get_or_compute(
                key=f"rdap:{domain}",
                ttl=self.RDAP_CACHE_TTL,
                fn=lambda: self._rdap.lookup(domain),
            )
        except Exception as exc:
            return ModuleResult.error(self.name, str(exc))

        if raw.get("_not_found"):
            return ModuleResult(
                module_name=self.name,
                value=None,
                confidence=1.0,
                data={"registered": False, "domain": domain},
                status=ModuleStatus.NOT_FOUND,
            )

        result = self._parse(raw)
        multiplier = self._age_multiplier(result.age_years or 0)

        return ModuleResult(
            module_name=self.name,
            value=multiplier,
            confidence=1.0,
            data=result.to_dict(),
            status=ModuleStatus.SUCCESS,
        )

    @staticmethod
    def _parse(raw: dict[str, Any]) -> RDAPResult:
        ldh_name: str | None = raw.get("ldhName")
        events: list[dict[str, Any]] = raw.get("events", [])
        entities: list[dict[str, Any]] = raw.get("entities", [])
        return RDAPResult(
            registered=True,
            creation_date=_parse_event(events, "registration"),
            expiry_date=_parse_event(events, "expiration"),
            last_changed_date=_parse_event(events, "last changed"),
            registrar=_extract_registrar(entities),
            domain_name=ldh_name,
            statuses=tuple(raw.get("status", [])),
            raw=raw,
        )

    @staticmethod
    def _age_multiplier(age_years: float) -> float:
        if age_years >= _AGE_20_PLUS:
            return _MULT_20_PLUS
        if age_years >= _AGE_10_PLUS:
            return _MULT_10_PLUS
        if age_years >= _AGE_5_PLUS:
            return _MULT_5_PLUS
        if age_years >= _AGE_1_PLUS:
            return _MULT_1_PLUS
        return _MULT_DEFAULT


def _parse_event(events: list[dict[str, Any]], action: str) -> datetime.date | None:
    for event in events:
        if event.get("eventAction") == action:
            raw = event.get("eventDate")
            if raw:
                try:
                    return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
                except (ValueError, TypeError):
                    pass
    return None


def _extract_registrar(entities: list[dict[str, Any]]) -> str | None:
    vcard: list[Any] | None = None
    for entity in entities:
        roles: list[str] = entity.get("roles", [])
        if "registrar" in roles:
            for entry in entity.get("vcardArray", []):
                if isinstance(entry, list):
                    vcard = entry
                    break
    if vcard:
        for item in vcard:
            if isinstance(item, list) and len(item) >= 3 and item[0] == "fn":
                return str(item[3])
    return None
