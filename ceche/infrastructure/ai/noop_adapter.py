from ceche.domain.ports import AIPort


class NoOpAIAdapter(AIPort):
    async def complete(self, prompt: str) -> str:
        return ""
