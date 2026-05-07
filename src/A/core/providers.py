"""LLM provider implementations for A-core.

Provides protocol, base class, and concrete providers:
- OpenAICompatibleProvider: Any OpenAI-compatible API (OpenAI, DeepSeek, HuggingFace)
- OllamaProvider: Local LLM inference via Ollama
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


# ── Core types ──────────────────────────────────────────────────────────────


@dataclass
class ToolCall:
    """A tool/function call requested by the LLM."""
    id: str
    type: str = "function"
    function: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Response from an LLM chat call, possibly with tool calls.

    Attributes:
        content: Text content from the LLM (empty if only tool calls)
        tool_calls: List of tool calls requested (None if text only)
        finish_reason: Why generation stopped ("stop", "tool_calls", "length")
        reasoning_content: Reasoning tokens (DeepSeek thinking mode). Must be
            echoed back in subsequent requests.
    """
    content: str = ""
    tool_calls: list[ToolCall] | None = None
    finish_reason: str = "stop"
    reasoning_content: str | None = None


class LLMProvider(Protocol):
    """Abstract LLM provider protocol."""

    def generate(self, prompt: str, **kwargs: Any) -> str: ...

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             **kwargs: Any) -> LLMResponse: ...

    async def generate_async(self, prompt: str, **kwargs: Any) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def supports_tools(self) -> bool: return False


# ── Base class ──────────────────────────────────────────────────────────────


class BaseProvider:
    """Base class for LLM providers with common functionality."""

    def __init__(self, model: str = "gpt-3.5-turbo", temperature: float = 0.7,
                 max_tokens: int = 1000):
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return self.__class__.__name__.replace("Provider", "").lower()

    @property
    def model(self) -> str:
        return self._model

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kwargs).content

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             **kwargs: Any) -> LLMResponse:
        prompt = self._build_chat_prompt(messages, tools)
        text = self._call_api(prompt, **kwargs)
        return LLMResponse(content=text)

    @property
    def supports_tools(self) -> bool:
        return False

    def _build_chat_prompt(self, messages: list[dict],
                           tools: list[dict] | None = None) -> str:
        """Convert messages + tools to a single prompt string (fallback for
        providers without native tool calling)."""
        parts = []
        if tools:
            parts.append("Available tools:")
            for t in tools:
                name = t.get("function", {}).get("name", "?")
                desc = t.get("function", {}).get("description", "")
                parts.append(f"  - {name}: {desc}")
            parts.append("")
            parts.append("To call a tool, respond with: TOOL_CALL: name | arg=val")
            parts.append("After receiving result, continue with your response.")
            parts.append("")
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.insert(0, content)
            elif role == "tool":
                parts.append(f"[Tool result: {content}]")
            else:
                parts.append(f"{role}: {content}")
        return "\n".join(parts)

    def _call_api(self, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError

    def _get_common_params(self) -> dict[str, Any]:
        return {
            "model": self._model,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }


# ── OpenAI-Compatible Provider (OpenAI, DeepSeek, HuggingFace, etc.) ────────

# Built-in provider configs. Users can add more by passing constructor args.
PROVIDER_CONFIGS: dict[str, dict[str, Any]] = {
    "openai": {
        "name": "openai",
        "model": "gpt-3.5-turbo",
        "base_url": None,
    },
    "deepseek": {
        "name": "deepseek",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
    },
    "huggingface": {
        "name": "huggingface",
        "model": "meta-llama/Llama-3.2-1B-Instruct",
        "base_url": "https://api-inference.huggingface.co/v1/",
    },
}


class OpenAICompatibleProvider(BaseProvider):
    """Provider for any OpenAI-compatible chat API.

    Supports OpenAI, DeepSeek, HuggingFace, and any other API that
    implements the OpenAI chat completions interface.

    Usage:
        provider = OpenAICompatibleProvider("deepseek")
        provider = OpenAICompatibleProvider("openai", api_key="sk-...")
        provider = OpenAICompatibleProvider(model="my-model",
                                            base_url="https://custom.endpoint/v1")
    """

    def __init__(
        self,
        provider_type: str = "openai",
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        base_url: str | None = None,
    ):
        # Load defaults from config if provider_type is known
        config = PROVIDER_CONFIGS.get(provider_type, {})
        resolved_model = model or config.get("model", "gpt-3.5-turbo")
        super().__init__(model=resolved_model, temperature=temperature,
                         max_tokens=max_tokens)
        self._provider_type = provider_type
        self._base_url = base_url if base_url is not None else config.get("base_url")
        self._api_key = api_key
        self._name = config.get("name", provider_type)
        self._client: Any = None

    @property
    def name(self) -> str:
        return self._name

    def _get_client(self):
        if self._client is not None:
            return self._client
        from openai import OpenAI
        kwargs: dict[str, Any] = {}
        key = self._api_key
        if not key:
            key = _resolve_api_key(self._provider_type)
        if key:
            kwargs["api_key"] = key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             **kwargs: Any) -> LLMResponse:
        params = self._get_common_params()
        params.update(kwargs)
        client = self._get_client()
        kwargs_inner: dict[str, Any] = {"model": self._model, "messages": messages}
        if tools:
            kwargs_inner["tools"] = tools
        kwargs_inner["temperature"] = params["temperature"]
        kwargs_inner["max_tokens"] = params["max_tokens"]

        try:
            response = client.chat.completions.create(**kwargs_inner)
        except Exception as e:
            raise RuntimeError(
                f"{self._name} API call failed: {e}"
            ) from e
        msg = response.choices[0].message

        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                ToolCall(id=tc.id, type="function",
                         function={"name": tc.function.name,
                                   "arguments": tc.function.arguments})
                for tc in msg.tool_calls
            ]

        reasoning = getattr(msg, "reasoning_content", None)
        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason or "stop",
            reasoning_content=reasoning,
        )

    @property
    def supports_tools(self) -> bool:
        return True

    async def generate_async(self, prompt: str, **kwargs: Any) -> str:
        params = self._get_common_params()
        params.update(kwargs)
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
        )
        return response.choices[0].message.content or ""


def _resolve_api_key(provider_type: str) -> str | None:
    """Resolve API key for a provider type from env/.env/keyring.

    Args:
        provider_type: Provider name ("openai", "deepseek", "huggingface")

    Returns:
        API key string or None
    """
    from A.core import keyring as _kr
    from A.core.paths import config_dir as _cd
    import os

    # Map provider type to env var name
    env_map = {
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "huggingface": "HF_TOKEN",
    }
    keyring_map = {
        "openai": ("A-core/openai_key", "api_key"),
        "deepseek": ("A-core/deepseek", "api_key"),
        "huggingface": ("A-core/huggingface", "token"),
    }

    # 1. Environment variable
    env_var = env_map.get(provider_type)
    if env_var:
        key = os.environ.get(env_var)
        if key:
            return key

    # 2. .env file
    env_file = _cd() / ".env"
    if env_file.exists():
        try:
            for line in open(env_file):
                line = line.strip()
                if line.startswith(env_var + "=") if env_var else False:
                    return line.split("=", 1)[1]
        except Exception:
            pass

    # 3. Keyring
    kr_config = keyring_map.get(provider_type)
    if kr_config:
        return _kr.get_password(kr_config[0], kr_config[1])

    return None


# ── Ollama Provider ─────────────────────────────────────────────────────────


class OllamaProvider(BaseProvider):
    """Ollama provider for local LLM inference.

    Connects to local Ollama server (default: http://localhost:11434).
    Uses the /api/generate endpoint (not OpenAI-compatible /v1).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama2",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ):
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "ollama"

    def _make_request(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        import httpx
        params = self._get_common_params()
        params.update(kwargs)
        payload = {
            "model": params["model"],
            "prompt": prompt,
            "temperature": params["temperature"],
            "max_tokens": params["max_tokens"],
            "stream": False,
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self._base_url}/api/generate",
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    def generate(self, prompt: str, **kwargs: Any) -> str:
        result = self._make_request(prompt, **kwargs)
        return result.get("response", "")

    async def generate_async(self, prompt: str, **kwargs: Any) -> str:
        import httpx
        import json as _json
        params = self._get_common_params()
        params.update(kwargs)
        payload = {
            "model": params["model"],
            "prompt": prompt,
            "temperature": params["temperature"],
            "max_tokens": params["max_tokens"],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                content=_json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")


__all__ = [
    "ToolCall",
    "LLMResponse",
    "LLMProvider",
    "BaseProvider",
    "OpenAICompatibleProvider",
    "OllamaProvider",
    "PROVIDER_CONFIGS",
]
