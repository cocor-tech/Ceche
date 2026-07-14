from __future__ import annotations

import asyncio
from typing import Any

from ceche.domain.ports import AIPort
from ceche.infrastructure.ai.orchestrator.blender import blend_result
from ceche.infrastructure.ai.orchestrator.budget import CostController
from ceche.infrastructure.ai.orchestrator.policy import RefinementPolicy, build_default_policy
from ceche.infrastructure.ai.prompts.catalog import get_prompt
from ceche.infrastructure.ai.prompts.parser import parse_response
from ceche.infrastructure.ai.tools.catalog import get_catalog
from ceche.infrastructure.ai.tools.sandbox import ToolResult


class AgentOrchestrator:
    AI_TIMEOUT = 10.0

    def __init__(
        self,
        ai: AIPort | None = None,
        policy: RefinementPolicy | None = None,
        budget: CostController | None = None,
    ) -> None:
        self._ai = ai
        self._policy = policy or build_default_policy()
        self._budget = budget or CostController()
        self._enabled = ai is not None

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def refine_module(
        self,
        module: str,
        context: dict[str, Any],
        original_value: float | None,
        original_confidence: float,
        original_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not self._ai:
            return None

        rule = self._find_rule(module)
        if rule is None:
            return None

        domain = context.get("domain_name", "unknown")
        if not self._budget.can_spend(domain, rule.max_cost):
            return None

        prompt = get_prompt(rule.prompt_id)
        if prompt is None:
            return None

        try:
            rendered = prompt.render(
                sld=context.get("sld", ""),
                word=context.get("last_word", context.get("sld", "")),
                tld=context.get("tld", ""),
                current_score=str(context.get("current_score", original_value or 0)),
                split=str(context.get("split", "")),
                frequencies=str(context.get("frequencies", "")),
                word_count=str(context.get("word_count", "0")),
                length=str(context.get("length", len(context.get("sld", "")))),
                registered=str(context.get("registered", True)),
                completeness_ratio=str(context.get("completeness_ratio", 1.0)),
                module_statuses=str(context.get("module_statuses", "")),
                domain=str(context.get("domain_name", "")),
                estimated_value=str(context.get("estimated_value", original_value or 0)),
                scarcity_base=str(context.get("scarcity_base", 0)),
                syllables=str(context.get("syllables", 0)),
                vowel_ratio=str(context.get("vowel_ratio", "")),
                max_cluster=str(context.get("max_cluster", "")),
                bigram_score=str(context.get("bigram_score", "")),
                freq=str(context.get("freq", "")),
            )

            raw_response = await asyncio.wait_for(
                self._ai.complete(rendered),
                timeout=self.AI_TIMEOUT,
            )

            parsed = parse_response(prompt.output_format, raw_response)
            ai_value = parsed.get("score") or parsed.get("value")
            ai_confidence = float(parsed.get("confidence", 0.5))

            self._budget.track(domain, rule.max_cost)

            return blend_result(
                original_value=original_value,
                original_confidence=original_confidence,
                ai_value=ai_value,
                ai_confidence=ai_confidence,
                original_data=original_data,
            )

        except asyncio.TimeoutError:
            self._budget.track(domain, 0.0)
            return None
        except Exception:
            return None

    def _find_rule(self, module: str) -> Any | None:
        for rule in self._policy.rules:
            if rule.module == module:
                return rule
        return None

    async def run_tool(self, name: str, params: dict[str, Any]) -> ToolResult:
        cat = get_catalog()
        return await cat.execute(name, params)

    def reset_for_domain(self, domain: str) -> None:
        self._budget.reset_domain(domain)
