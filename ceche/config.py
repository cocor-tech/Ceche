from __future__ import annotations

from dataclasses import dataclass

import dotenv

dotenv.load_dotenv()


@dataclass
class Config:
    google_cse_key: str = ""
    google_cse_cx: str = ""
    brave_key: str = ""
    opr_key: str = ""
    cache_path: str = "cache.db"
    fresh: bool = False
    concurrency: int = 10
    format: str = "pretty"
    cache_enabled: bool = True
    ai_enabled: bool = False
    ai_temperature: float = 0.1
    ai_max_tokens: int = 150
    m6_max_tokens: int = 500
    profile: str = ""

    @classmethod
    def load(cls) -> Config:
        from ceche.infrastructure.config.loader import ConfigLoader
        return ConfigLoader().load()
