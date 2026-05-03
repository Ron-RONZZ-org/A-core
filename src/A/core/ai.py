"""LLM provider abstraction for A-core.

Provides abstract protocol and concrete implementations for:
- HuggingFace (cloud - free tier available)
- DeepSeek (cloud - OpenAI compatible)
- Ollama (local)

Usage:
    from A.core.ai import get_provider, save_api_key

    # Get provider (defaults to first available key, else Ollama)
    provider = get_provider("huggingface")
    
    # Generate text
    result = provider.generate("Summarize: The meeting is at 3pm tomorrow.")

API Key Sources (in priority order):
1. Environment variable: HF_TOKEN / DEEPSEEK_API_KEY
2. .env file in config directory
3. System keyring (for persistent storage)
"""

from __future__ import annotations

import os
from abc import abstractmethod
from pathlib import Path
from typing import Protocol, Awaitable, Any

from A.core import keyring as _keyring
from A.core.paths import config_dir


class LLMProvider(Protocol):
    """Abstract LLM provider - implement for OpenAI, Ollama, etc."""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt (synchronous).

        Args:
            prompt: Input prompt/text
            **kwargs: Provider-specific parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response
        """
        ...

    async def generate_async(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt (asynchronous).

        Args:
            prompt: Input prompt/text
            **kwargs: Provider-specific parameters

        Returns:
            Generated text response
        """
        ...

    @property
    def name(self) -> str:
        """Provider name for display."""
        ...


class BaseProvider:
    """Base class for LLM providers with common functionality."""

    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ):
        """Initialize provider with default parameters.

        Args:
            model: Model name to use
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
        """
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        """Provider name for display."""
        return self.__class__.__name__.replace("Provider", "").lower()

    @property
    def model(self) -> str:
        """Model name."""
        return self._model

    def _get_common_params(self) -> dict[str, Any]:
        """Get common generation parameters."""
        return {
            "model": self._model,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }


class OpenAIProvider(BaseProvider):
    """OpenAI provider using the openai library.

    Requires API key stored in system keyring.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        base_url: str | None = None,
        organization: str | None = None,
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (None = read from keyring)
            model: Model name (gpt-3.5-turbo, gpt-4, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            base_url: Custom API base URL (for compatible APIs)
            organization: OpenAI organization ID
        """
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self._api_key = api_key
        self._base_url = base_url
        self._organization = organization
        self._client: Any = None

    @property
    def name(self) -> str:
        """Provider name for display."""
        return "openai"

    def _get_client(self) -> Any:
        """Get or create OpenAI client."""
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai library not installed. Install with: pip install openai"
            )

        kwargs: dict[str, Any] = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if self._organization:
            kwargs["organization"] = self._organization

        self._client = OpenAI(**kwargs)
        return self._client

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using OpenAI API.

        Args:
            prompt: Input prompt
            **kwargs: Override parameters (model, temperature, max_tokens)

        Returns:
            Generated text
        """
        params = self._get_common_params()
        params.update(kwargs)

        client = self._get_client()
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            **params,
        )
        return response.choices[0].message.content or ""

    async def generate_async(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using OpenAI API (async).

        Args:
            prompt: Input prompt
            **kwargs: Override parameters

        Returns:
            Generated text
        """
        params = self._get_common_params()
        params.update(kwargs)

        client = self._get_client()
        response = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            **params,
        )
        return response.choices[0].message.content or ""


class OllamaProvider(BaseProvider):
    """Ollama provider for local LLM inference.

    Connects to local Ollama server (default: http://localhost:11434).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama2",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ):
        """Initialize Ollama provider.

        Args:
            base_url: Ollama server URL
            model: Model name (llama2, mistral, codellama, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        """
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        """Provider name for display."""
        return "ollama"

    def _make_request(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Make request to Ollama API."""
        import json

        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx library not installed. Install with: pip install httpx"
            )

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
        """Generate text using Ollama API.

        Args:
            prompt: Input prompt
            **kwargs: Override parameters

        Returns:
            Generated text
        """
        result = self._make_request(prompt, **kwargs)
        return result.get("response", "")

    async def generate_async(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using Ollama API (async).

        Args:
            prompt: Input prompt
            **kwargs: Override parameters

        Returns:
            Generated text
        """
        import json

        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx library not installed. Install with: pip install httpx"
            )

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
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")


class HuggingFaceProvider(BaseProvider):
    """HuggingFace provider using Inference API.

    Supports free tier and premium endpoints.
    Requires HF_TOKEN environment variable or .env file.
    """

    DEFAULT_MODEL = "meta-llama/Llama-3.2-1B-Instruct"

    def __init__(
        self,
        api_token: str | None = None,
        model: str = "meta-llama/Llama-3.2-1B-Instruct",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ):
        """Initialize HuggingFace provider.

        Args:
            api_token: HuggingFace API token (None = read from env/.env)
            model: Model name (default: meta-llama/Llama-3.2-1B-Instruct)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        """
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self._api_token = api_token or _get_huggingface_token()
        self._client: Any = None

    @property
    def name(self) -> str:
        """Provider name for display."""
        return "huggingface"

    def _get_client(self) -> Any:
        """Get or create HuggingFace inference client."""
        if self._client is not None:
            return self._client

        try:
            from huggingface_hub import InferenceClient
        except ImportError:
            raise ImportError(
                "huggingface_hub not installed. Install with: pip install huggingface_hub"
            )

        self._client = InferenceClient(token=self._api_token)
        return self._client

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using HuggingFace Inference API.

        Args:
            prompt: Input prompt
            **kwargs: Override parameters (temperature, max_tokens, model)

        Returns:
            Generated text
        """
        params = self._get_common_params()
        params.update(kwargs)

        client = self._get_client()
        # Use chat completion endpoint for instruction-following models
        response = client.chat.completions(
            model=params["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
        )
        return response.choices[0].message.content or ""

    async def generate_async(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using HuggingFace Inference API (async).

        Args:
            prompt: Input prompt
            **kwargs: Override parameters

        Returns:
            Generated text
        """
        import asyncio

        # Run sync generate in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate, prompt, **kwargs)


class DeepSeekProvider(BaseProvider):
    """DeepSeek provider using their API (OpenAI-compatible).

    Requires DEEPSEEK_API_KEY environment variable or .env file.
    """

    DEFAULT_MODEL = "deepseek-chat"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        base_url: str = "https://api.deepseek.com/v1",
    ):
        """Initialize DeepSeek provider.

        Args:
            api_key: DeepSeek API key (None = read from env/.env)
            model: Model name (deepseek-chat, deepseek-coder, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            base_url: API base URL (default: https://api.deepseek.com/v1)
        """
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self._api_key = api_key or _get_deepseek_key()
        self._base_url = base_url.rstrip("/")
        self._client: Any = None

    @property
    def name(self) -> str:
        """Provider name for display."""
        return "deepseek"

    def _get_client(self) -> Any:
        """Get or create DeepSeek client."""
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai library not installed. Install with: pip install openai"
            )

        self._client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
        )
        return self._client

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using DeepSeek API.

        Args:
            prompt: Input prompt
            **kwargs: Override parameters (model, temperature, max_tokens)

        Returns:
            Generated text
        """
        params = self._get_common_params()
        params.update(kwargs)

        client = self._get_client()
        response = client.chat.completions.create(
            model=params["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
        )
        return response.choices[0].message.content or ""

    async def generate_async(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using DeepSeek API (async).

        Args:
            prompt: Input prompt
            **kwargs: Override parameters

        Returns:
            Generated text
        """
        params = self._get_common_params()
        params.update(kwargs)

        client = self._get_client()
        response = await client.chat.completions.create(
            model=params["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
        )
        return response.choices[0].message.content or ""


# Default provider storage
_default_provider: str = "huggingface"


# ============================================================================
# Environment and .env file loading
# ============================================================================


def _load_env_file() -> dict[str, str]:
    """Load .env file from config directory.

    Returns:
        Dict of environment variable names to values
    """
    env_file = config_dir() / ".env"
    if not env_file.exists():
        return {}

    env_vars: dict[str, str] = {}
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except Exception:
        pass
    return env_vars


def _get_huggingface_token() -> str | None:
    """Get HuggingFace token from env or .env file.

    Priority: env var > .env file > keyring
    """
    # Check environment variable first
    token = os.environ.get("HF_TOKEN")
    if token:
        return token

    # Check .env file
    env_vars = _load_env_file()
    token = env_vars.get("HF_TOKEN")
    if token:
        return token

    # Fall back to keyring
    return _keyring.get_password("A-core/huggingface", "token")


def _get_deepseek_key() -> str | None:
    """Get DeepSeek API key from env or .env file.

    Priority: env var > .env file > keyring
    """
    # Check environment variable first
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key

    # Check .env file
    env_vars = _load_env_file()
    key = env_vars.get("DEEPSEEK_API_KEY")
    if key:
        return key

    # Fall back to keyring
    return _keyring.get_password("A-core/deepseek", "api_key")


def _get_openai_key() -> str | None:
    """Get OpenAI API key from env or .env file.

    Priority: env var > .env file > keyring
    """
    # Check environment variable first
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    # Check .env file
    env_vars = _load_env_file()
    key = env_vars.get("OPENAI_API_KEY")
    if key:
        return key

    # Fall back to keyring (existing behavior)
    return _keyring.get_password("A-core/openai_key", "api_key")


def save_api_key(api_key: str, provider: str = "openai", profile: str = "default") -> bool:
    """Save API key to system keyring.

    Args:
        api_key: API key
        provider: Provider name ("openai", "huggingface", "deepseek")
        profile: Profile name (for multiple keys)

    Returns:
        True if saved successfully
    """
    service = f"A-core/{profile}/{provider}_key"
    key_name = "api_key" if provider != "huggingface" else "token"
    return _keyring.set_password(service, key_name, api_key)


def get_api_key(provider: str = "openai", profile: str = "default") -> str | None:
    """Get API key from system keyring.

    Args:
        provider: Provider name ("openai", "huggingface", "deepseek")
        profile: Profile name

    Returns:
        API key or None if not found
    """
    service = f"A-core/{profile}/{provider}_key"
    key_name = "api_key" if provider != "huggingface" else "token"
    return _keyring.get_password(service, key_name)


def set_default_provider(provider_type: str) -> None:
    """Set the default provider type.

    Args:
        provider_type: "huggingface", "deepseek", "openai", or "ollama"
    """
    global _default_provider
    valid = ("huggingface", "deepseek", "openai", "ollama")
    if provider_type not in valid:
        raise ValueError(f"Unknown provider type: {provider_type}. Valid: {valid}")
    _default_provider = provider_type


def get_default_provider() -> str:
    """Get the default provider type."""
    return _default_provider


def get_provider(
    provider_type: str | None = None,
    **kwargs: Any,
) -> LLMProvider:
    """Factory function to get an LLM provider.

    Args:
        provider_type: Provider type ("huggingface", "deepseek", "openai", "ollama", or None for default)
        **kwargs: Provider-specific parameters

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider type is unknown or API key unavailable
    """
    global _default_provider

    # Determine provider type
    if provider_type is None:
        provider_type = _default_provider

    # Try auto-detect if no preference - try in order of priority
    if provider_type == "auto":
        # Priority: HuggingFace (free tier) > DeepSeek > OpenAI > Ollama
        if _get_huggingface_token():
            provider_type = "huggingface"
        elif _get_deepseek_key():
            provider_type = "deepseek"
        elif _get_openai_key():
            provider_type = "openai"
        else:
            provider_type = "ollama"

    # Create provider based on type
    if provider_type == "huggingface":
        api_token = kwargs.pop("api_token", None) or _get_huggingface_token()
        if not api_token:
            raise ValueError(
                "HuggingFace token not found. Set with:\n"
                "  1. Environment: export HF_TOKEN=your-token\n"
                "  2. .env file: HF_TOKEN=your-token in ~/.config/A/.env\n"
                "  3. Keyring: python -c \"from A.core.ai import save_api_key; "
                "save_api_key('your-token', 'huggingface')\""
            )
        return HuggingFaceProvider(api_token=api_token, **kwargs)

    elif provider_type == "deepseek":
        api_key = kwargs.pop("api_key", None) or _get_deepseek_key()
        if not api_key:
            raise ValueError(
                "DeepSeek API key not found. Set with:\n"
                "  1. Environment: export DEEPSEEK_API_KEY=your-key\n"
                "  2. .env file: DEEPSEEK_API_KEY=your-key in ~/.config/A/.env\n"
                "  3. Keyring: python -c \"from A.core.ai import save_api_key; "
                "save_api_key('your-key', 'deepseek')\""
            )
        return DeepSeekProvider(api_key=api_key, **kwargs)

    elif provider_type == "openai":
        api_key = kwargs.pop("api_key", None) or _get_openai_key()
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Set with:\n"
                "  1. Environment: export OPENAI_API_KEY=your-key\n"
                "  2. .env file: OPENAI_API_KEY=your-key in ~/.config/A/.env\n"
                "  3. Keyring: python -c \"from A.core.ai import save_api_key; "
                "save_api_key('your-key', 'openai')\""
            )
        return OpenAIProvider(api_key=api_key, **kwargs)

    elif provider_type == "ollama":
        return OllamaProvider(**kwargs)

    else:
        raise ValueError(f"Unknown provider type: {provider_type}")


__all__ = [
    "LLMProvider",
    "BaseProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "HuggingFaceProvider",
    "DeepSeekProvider",
    "get_provider",
    "save_api_key",
    "get_api_key",
    "set_default_provider",
    "get_default_provider",
]