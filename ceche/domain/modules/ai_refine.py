from __future__ import annotations

from typing import Any

from ceche.domain.ports import AIPort


async def ai_refine_module(
    ai: AIPort | None,
    module_name: str,
    context: dict[str, Any],
    prompt: str,
) -> str:
    if ai is None:
        return ""
    try:
        return await ai.complete(prompt)
    except Exception:
        return ""
