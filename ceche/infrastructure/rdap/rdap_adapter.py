from __future__ import annotations

from typing import Any

import httpx

from ceche.domain.models import ExternalServiceError
from ceche.domain.ports import RDAPPort

RDAP_BOOTSTRAP_URL = "https://rdap.org/domain/{domain}"
_HTTP_NOT_FOUND = 404
_HTTP_OK = 200


class RDAPAdapter(RDAPPort):
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=15.0)

    async def lookup(self, domain: str) -> dict[str, Any]:
        url = RDAP_BOOTSTRAP_URL.format(domain=domain)
        try:
            resp = await self._client.get(url, headers={"Accept": "application/rdap+json"})
        except httpx.TimeoutException:
            raise ExternalServiceError(
                service="rdap",
                message=f"timeout querying {domain}",
            ) from None
        except httpx.RequestError as exc:
            raise ExternalServiceError(
                service="rdap",
                message=f"request failed for {domain}: {exc}",
            ) from exc

        if resp.status_code == _HTTP_NOT_FOUND:
            return {"_not_found": True, "domain": domain, "error_code": _HTTP_NOT_FOUND}

        if resp.status_code != _HTTP_OK:
            raise ExternalServiceError(
                service="rdap",
                message=f"unexpected status {resp.status_code} for {domain}",
                status_code=resp.status_code,
            )

        try:
            data: dict[str, Any] = resp.json()
        except ValueError as exc:
            raise ExternalServiceError(
                service="rdap",
                message=f"invalid JSON for {domain}: {exc}",
            ) from exc

        return data
