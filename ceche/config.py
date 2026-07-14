from __future__ import annotations

import os
from dataclasses import dataclass

import dotenv

dotenv.load_dotenv()


@dataclass
class Config:
    google_cse_key: str
    google_cse_cx: str
    brave_key: str
    opr_key: str
    cache_path: str
    fresh: bool

    @classmethod
    def load(cls) -> Config:
        return cls(
            google_cse_key=os.getenv("CECHE_GOOGLE_CSE_KEY", ""),
            google_cse_cx=os.getenv("CECHE_GOOGLE_CSE_CX", ""),
            brave_key=os.getenv("CECHE_BRAVE_KEY", ""),
            opr_key=os.getenv("CECHE_OPR_KEY", ""),
            cache_path=os.getenv("CECHE_CACHE_PATH", "cache.db"),
            fresh=os.getenv("CECHE_FRESH", "").lower() in ("1", "true", "yes"),
        )
