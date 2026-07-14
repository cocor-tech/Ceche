from __future__ import annotations

import httpx

from ceche.domain.ports import AIPort


class OpenAIAdapter(AIPort):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._key = api_key
        self._model = model
        self._url = "https://api.openai.com/v1/chat/completions"

    async def complete(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a domain name analysis expert. "
                        "Respond concisely with only the requested format."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 200,
            "temperature": 0.1,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(self._url, headers=headers, json=payload)
                if resp.status_code != 200:
                    return ""
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return str(choices[0].get("message", {}).get("content", ""))
        except Exception:
            pass
        return ""
