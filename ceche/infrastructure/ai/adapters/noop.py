from ceche.infrastructure.ai.adapters.base import AIResponse, BaseAIAdapter


class NoOpAdapter(BaseAIAdapter):
    @property
    def model_name(self) -> str:
        return "none"

    async def complete(self, prompt: str, system: str = "") -> AIResponse:
        return AIResponse(content="", model="none")

    async def health_check(self) -> bool:
        return False
