from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

import jwt


@dataclass
class AgentJWTClaims:
    sub: str
    iat: int
    exp: int
    provider: str
    jti: str
    ttl_hours: int
    grantor: str
    permissions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub": self.sub,
            "iat": self.iat,
            "exp": self.exp,
            "provider": self.provider,
            "jti": self.jti,
            "ttl_hours": self.ttl_hours,
            "grantor": self.grantor,
            "permissions": self.permissions,
        }


class AgentJWT:
    MAX_TTL_HOURS = 24

    def __init__(
        self,
        private_key_pem: str | None = None,
        public_key_pem: str | None = None,
    ) -> None:
        self._private_key = private_key_pem
        self._public_key = public_key_pem

    def create(
        self,
        sub: str,
        provider: str,
        grantor: str,
        ttl_hours: int = 1,
        permissions: list[str] | None = None,
    ) -> str:
        if not self._private_key:
            raise ValueError("private key required for signing")
        ttl_hours = min(ttl_hours, self.MAX_TTL_HOURS)
        now = int(time.time())
        claims = AgentJWTClaims(
            sub=sub,
            iat=now,
            exp=now + ttl_hours * 3600,
            provider=provider,
            jti=str(uuid.uuid4()),
            ttl_hours=ttl_hours,
            grantor=grantor,
            permissions=permissions or ["appraise"],
        )
        return jwt.encode(claims.to_dict(), self._private_key, algorithm="RS256")

    def verify(self, token: str) -> AgentJWTClaims:
        if not self._public_key:
            raise ValueError("public key required for verification")
        payload: dict[str, Any] = jwt.decode(
            token, self._public_key, algorithms=["RS256"],
        )
        return AgentJWTClaims(
            sub=str(payload["sub"]),
            iat=int(payload["iat"]),
            exp=int(payload["exp"]),
            provider=str(payload["provider"]),
            jti=str(payload["jti"]),
            ttl_hours=int(payload["ttl_hours"]),
            grantor=str(payload["grantor"]),
            permissions=[str(p) for p in payload.get("permissions", ["appraise"])],
        )

    @staticmethod
    def extract_claims_unsigned(token: str) -> AgentJWTClaims | None:
        try:
            payload: dict[str, Any] = jwt.decode(
                token, options={"verify_signature": False},
            )
            return AgentJWTClaims(
                sub=str(payload["sub"]),
                iat=int(payload["iat"]),
                exp=int(payload["exp"]),
                provider=str(payload["provider"]),
                jti=str(payload["jti"]),
                ttl_hours=int(payload["ttl_hours"]),
                grantor=str(payload["grantor"]),
                permissions=[str(p) for p in payload.get("permissions", ["appraise"])],
            )
        except Exception:
            return None
