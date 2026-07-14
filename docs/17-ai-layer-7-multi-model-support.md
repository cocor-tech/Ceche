# Layer 7 — Multi-Model Support

## Overview

The AI layer abstracts provider-specific APIs behind a unified interface. Any model — OpenAI, Anthropic, local Ollama, or a custom provider — plugs in with zero changes to modules, prompts, or the orchestrator. The system detects available providers at startup and selects the best one based on cost, capability, and availability.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Multi-Model Layer                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                     BaseAIAdapter (ABC)                       │    │
│  │  async complete(prompt, tools=None) → AIResponse              │    │
│  │  async health_check() → bool                                  │    │
│  │  model_name: str                                              │    │
│  │  cost_per_1k_tokens: float                                    │    │
│  └──────────────────────────────────────────────────────────────┘    │
│         │                │                │                │         │
│  ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐  │
│  │ OpenAI      │ │ Anthropic   │ │ Ollama      │ │ Custom      │  │
│  │ Adapter     │ │ Adapter     │ │ Adapter     │ │ Adapter     │  │
│  │             │ │             │ │             │ │             │  │
│  │ gpt-4o      │ │ claude-3    │ │ llama3      │ │ openrouter  │  │
│  │ gpt-4o-mini │ │ claude-3.5  │ │ mistral     │ │ groq        │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                  ModelSelector                                │    │
│  │  select(preferred, fallback, available) → BaseAIAdapter      │    │
│  │  Rules: cost budget, capability match, health check          │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

## Unified Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class AIResponse:
    content: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    tool_calls: list[dict] = field(default_factory=list)

@dataclass
class ToolCallRequest:
    name: str
    arguments: dict

class BaseAIAdapter(ABC):
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str = "",
        tools: list[dict] | None = None,
        max_tokens: int = 200,
        temperature: float = 0.1,
    ) -> AIResponse:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @property
    @abstractmethod
    def cost_per_1k_input(self) -> float:
        ...

    @property
    @abstractmethod
    def cost_per_1k_output(self) -> float:
        ...
```

## Adapter Implementations

### OpenAI Adapter

```python
class OpenAIAdapter(BaseAIAdapter):
    model_name = "gpt-4o-mini"
    cost_per_1k_input = 0.00015    # $0.15 / 1M tokens
    cost_per_1k_output = 0.00060   # $0.60 / 1M tokens

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._key = api_key
        self._model = model
        self._url = "https://api.openai.com/v1/chat/completions"

    async def complete(self, prompt, system="", tools=None, max_tokens=200, temperature=0.1):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
                json=payload,
            )
            data = resp.json()
            usage = data.get("usage", {})
            return AIResponse(
                content=data["choices"][0]["message"]["content"],
                model=self._model,
                tokens_in=usage.get("prompt_tokens", 0),
                tokens_out=usage.get("completion_tokens", 0),
                cost_usd=self._compute_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                latency_ms=0,  # set by caller
            )
```

### Anthropic Adapter

```python
class AnthropicAdapter(BaseAIAdapter):
    model_name = "claude-3-haiku"
    cost_per_1k_input = 0.00025     # $0.25 / 1M tokens
    cost_per_1k_output = 0.00125    # $1.25 / 1M tokens

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        self._key = api_key
        self._model = model
        self._url = "https://api.anthropic.com/v1/messages"

    async def complete(self, prompt, system="", tools=None, max_tokens=200, temperature=0.1):
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if tools:
            payload["tools"] = self._convert_tools(tools)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                self._url,
                headers={
                    "x-api-key": self._key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            data = resp.json()
            usage = data.get("usage", {})
            return AIResponse(
                content=data["content"][0]["text"],
                model=self._model,
                tokens_in=usage.get("input_tokens", 0),
                tokens_out=usage.get("output_tokens", 0),
                cost_usd=self._compute_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0)),
                latency_ms=0,
            )

    @staticmethod
    def _convert_tools(openai_tools: list[dict]) -> list[dict]:
        """Convert OpenAI function schemas to Anthropic tool format."""
        ...
```

### Ollama Adapter (Local — No Key, No Cost)

```python
class OllamaAdapter(BaseAIAdapter):
    model_name = "llama3"
    cost_per_1k_input = 0.0     # $0 — local model
    cost_per_1k_output = 0.0    # $0 — local model

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434"):
        self._model = model
        self._url = f"{base_url}/api/chat"

    async def complete(self, prompt, system="", tools=None, max_tokens=200, temperature=0.1):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._url,
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            )
            data = resp.json()
            return AIResponse(
                content=data["message"]["content"],
                model=self._model,
                tokens_in=data.get("prompt_eval_count", 0),
                tokens_out=data.get("eval_count", 0),
                cost_usd=0.0,   # zero cost for local model
                latency_ms=0,
            )
```

**Note:** Ollama has limited function-calling support. For tool-intensive prompts (M6 disambiguation), the orchestrator falls back to OpenAI/Anthropic if available. For simple classification prompts (M7, M8, M11, M16), Ollama handles them fine.

### NoOp Adapter

```python
class NoOpAdapter(BaseAIAdapter):
    model_name = "none"
    cost_per_1k_input = 0.0
    cost_per_1k_output = 0.0

    async def complete(self, prompt, system="", tools=None, max_tokens=200, temperature=0.1):
        return AIResponse(content="", model="none", tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=0)

    async def health_check(self) -> bool:
        return False
```

The NoOp adapter returns empty responses, causing the orchestrator to use deterministic results unchanged. This is the default when no AI provider is configured.

## Model Selector

```python
class ModelSelector:
    def __init__(self, adapters: list[BaseAIAdapter]):
        self._adapters = adapters

    async def select(self, requires_tools: bool = False) -> BaseAIAdapter:
        for adapter in self._adapters:
            if isinstance(adapter, NoOpAdapter):
                continue
            if requires_tools and isinstance(adapter, OllamaAdapter):
                continue  # Ollama doesn't reliably support function calling
            if await adapter.health_check():
                return adapter
        return NoOpAdapter()

    def best_for_cost(self) -> BaseAIAdapter:
        """Return cheapest healthy adapter."""
        candidates = [a for a in self._adapters
                      if not isinstance(a, NoOpAdapter)
                      and a.model_name != "none"]
        candidates.sort(key=lambda a: a.cost_per_1k_input)
        return candidates[0] if candidates else NoOpAdapter()

    def best_for_quality(self) -> BaseAIAdapter:
        """Return highest-quality healthy adapter."""
        quality_order = ["gpt-4o", "claude-3.5", "gpt-4o-mini", "claude-3", "llama3", "mistral"]
        for name in quality_order:
            for adapter in self._adapters:
                if name in adapter.model_name.lower():
                    return adapter
        return NoOpAdapter()
```

## Configuration

```toml
# ceche.toml
[ai]
provider = "auto"              # "auto" | "openai" | "anthropic" | "ollama" | "none"
model = "gpt-4o-mini"          # optional override

[ai.providers.openai]
api_key_env = "OPENAI_API_KEY"
model = "gpt-4o-mini"

[ai.providers.anthropic]
api_key_env = "ANTHROPIC_API_KEY"
model = "claude-3-haiku-20240307"

[ai.providers.ollama]
base_url = "http://localhost:11434"
model = "llama3"

[ai.selection]
strategy = "cost_first"        # "cost_first" | "quality_first" | "availability"
fallback_chain = ["ollama", "none"]
allow_tool_fallback = true     # if ollama can't use tools, try openai
```

### Behavior by Strategy

| Strategy | Priority | Use Case |
|---|---|---|
| `cost_first` | Cheapest available first, fallback upward | High volume, cost-sensitive |
| `quality_first` | Best quality first, fallback downward | Low volume, accuracy-critical |
| `availability` | Any healthy provider, prefer fast | Development, testing |

### Auto-Detection

At startup, the system probes each configured provider:

```python
async def detect_adapters(config) -> list[BaseAIAdapter]:
    adapters = []
    if config.openai_api_key:
        adapters.append(OpenAIAdapter(config.openai_api_key, config.openai_model))
    if config.anthropic_api_key:
        adapters.append(AnthropicAdapter(config.anthropic_api_key, config.anthropic_model))
    if config.ollama_enabled:
        adapters.append(OllamaAdapter(config.ollama_model, config.ollama_base_url))
    if not adapters:
        adapters.append(NoOpAdapter())
    return adapters
```

## Tool Compatibility Matrix

| Feature | OpenAI | Anthropic | Ollama |
|---|---|---|---|
| Function calling (structured) | ✅ Native | ✅ Native (converted) | ⚠️ Limited |
| System messages | ✅ | ✅ (separate param) | ✅ |
| JSON mode | ✅ | ❌ (parse text) | ❌ |
| Streaming | ✅ | ✅ | ✅ |
| Temperature control | ✅ | ✅ | ✅ |
| Max tokens | ✅ | ✅ | ✅ |
| Free tier available | ❌ | ❌ | ✅ (local) |

### Handling Ollama's Tool Limitations

For prompts requiring tools (M6 disambiguation), the orchestrator:

1. Tries the primary adapter with tools
2. If Ollama is primary and fails:
   - Checks if `allow_tool_fallback` is enabled
   - Falls back to OpenAI/Anthropic for this specific call
   - Logs the fallback for monitoring
3. If no tool-capable adapter available:
   - Sends tools as text descriptions in the prompt
   - Expects the LLM to reason and respond without actual function calls
   - Reduced accuracy but still functional

## Prompt Format Adapters

Each adapter has a prompt formatter that handles provider-specific quirks:

```python
class PromptFormatter:
    @staticmethod
    def for_openai(prompt: Prompt, context: dict) -> dict:
        return {
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user_template.format(**context)},
            ],
            "tools": prompt.tools if prompt.tools_allowed else None,
        }

    @staticmethod
    def for_anthropic(prompt: Prompt, context: dict) -> dict:
        return {
            "system": prompt.system,
            "messages": [
                {"role": "user", "content": prompt.user_template.format(**context)},
            ],
            "tools": _convert_openai_tools_to_anthropic(prompt.tools) if prompt.tools_allowed else None,
        }

    @staticmethod
    def for_ollama(prompt: Prompt, context: dict) -> dict:
        # Ollama doesn't support tools natively — embed them in the prompt
        user_msg = prompt.user_template.format(**context)
        if prompt.tools_allowed:
            tool_descriptions = "\n".join(
                f"Tool: {t.name} - {t.description}" for t in prompt.tools_allowed
            )
            user_msg = f"{user_msg}\n\nAvailable tools:\n{tool_descriptions}\nCall tools with: TOOL:name(args)"
        return {
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": user_msg},
            ],
        }
```

## Implementation Files

```
ceche/infrastructure/ai/
├── adapters/
│   ├── __init__.py
│   ├── base.py             # BaseAIAdapter, AIResponse, ToolCallRequest
│   ├── openai.py           # OpenAIAdapter
│   ├── anthropic.py        # AnthropicAdapter
│   ├── ollama.py           # OllamaAdapter (local, free)
│   ├── noop.py             # NoOpAdapter (existing, move here)
│   └── formatter.py        # PromptFormatter (provider-specific formatting)
├── selector.py             # ModelSelector
└── detection.py            # Auto-detect available providers
```
