from __future__ import annotations

from typing import Any

from ceche.domain.models import ModuleResult, ModuleStatus
from ceche.domain.modules.base import BaseModule
from ceche.domain.ports import RDAPPort

_CANDIDATE_TLDS = ("com", "net", "org", "co", "io", "app", "dev", "xyz")


class M10CrossTLD(BaseModule):
    name = "m10_cross_tld"

    def __init__(self, rdap: RDAPPort) -> None:
        self._rdap = rdap

    async def run(self, context: dict[str, Any]) -> ModuleResult:
        domain: str | None = context.get("domain_name")
        if not domain:
            return ModuleResult.error(self.name, "no domain_name in context")

        tld: str | None = context.get("tld")
        parts = domain.rsplit(".", 1)
        sld = parts[0]

        variants: dict[str, str] = {}
        com_active = False

        for candidate in _CANDIDATE_TLDS:
            if candidate == tld:
                continue
            candidate_domain = f"{sld}.{candidate}"
            try:
                raw = await self._rdap.lookup(candidate_domain)
            except Exception:
                continue
            if raw.get("_not_found"):
                continue
            variants[candidate] = "registered"
            if candidate == "com":
                com_active = True

        is_com = (tld or "").lower().lstrip(".") == "com"
        penalty = 1.0

        if is_com:
            pass
        elif com_active:
            penalty = 0.5

        return ModuleResult(
            module_name=self.name,
            value=penalty,
            confidence=1.0,
            data={
                "variants": variants,
                "com_active": com_active,
                "is_com": is_com,
                "multiplier": penalty,
            },
            status=ModuleStatus.SUCCESS,
        )
