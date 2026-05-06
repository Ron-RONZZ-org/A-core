"""LLM provider abstraction for A-core.

Provider factory, API key management, and configuration.
Concrete provider implementations live in A.core.providers.

Usage:
    from A.core.ai import get_provider, save_api_key

    provider = get_provider("huggingface")
    result = provider.generate("Summarize: The meeting is at 3pm tomorrow.")

API Key Sources (in priority order):
1. Environment variable: HF_TOKEN / DEEPSEEK_API_KEY / OPENAI_API_KEY
2. .env file in config directory
3. System keyring (for persistent storage)
"""

from __future__ import annotations

import os
from typing import Any

from A.core import keyring as _keyring
from A.core.paths import config_dir
from A.core.providers import (
    LLMProvider,
    OpenAICompatibleProvider,
    OllamaProvider,
)


# Default provider storage
_default_provider: str = "huggingface"


# ============================================================================
# Environment and .env file loading
# ============================================================================


def _load_env_file() -> dict[str, str]:
    """Load .env file from config directory."""
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
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    env_vars = _load_env_file()
    token = env_vars.get("HF_TOKEN")
    if token:
        return token
    return _keyring.get_password("A-core/huggingface", "token")


def _get_deepseek_key() -> str | None:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    env_vars = _load_env_file()
    key = env_vars.get("DEEPSEEK_API_KEY")
    if key:
        return key
    return _keyring.get_password("A-core/deepseek", "api_key")


def _get_openai_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    env_vars = _load_env_file()
    key = env_vars.get("OPENAI_API_KEY")
    if key:
        return key
    return _keyring.get_password("A-core/openai_key", "api_key")


# ============================================================================
# API key management
# ============================================================================


def save_api_key(api_key: str, provider: str = "openai",
                 profile: str = "default") -> bool:
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


# ============================================================================
# Provider selection
# ============================================================================


def set_default_provider(provider_type: str) -> None:
    """Set the default provider type.

    Args:
        provider_type: "huggingface", "deepseek", "openai", or "ollama"

    Raises:
        ValueError: If provider type is unknown
    """
    global _default_provider
    valid = ("huggingface", "deepseek", "openai", "ollama")
    if provider_type not in valid:
        raise ValueError(
            f"Unknown provider type: {provider_type}. Valid: {valid}"
        )
    _default_provider = provider_type


def get_default_provider() -> str:
    """Get the default provider type."""
    return _default_provider


def get_provider(provider_type: str | None = None, **kwargs: Any) -> LLMProvider:
    """Factory function to get an LLM provider.

    Args:
        provider_type: Provider type ("huggingface", "deepseek", "openai",
                       "ollama", or None for default, or "auto")
        **kwargs: Provider-specific parameters (model, base_url, etc.)

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider type is unknown or API key unavailable
    """
    global _default_provider

    if provider_type is None:
        provider_type = _default_provider

    # Auto-detect: try providers in order of priority
    if provider_type == "auto":
        if _get_huggingface_token():
            provider_type = "huggingface"
        elif _get_deepseek_key():
            provider_type = "deepseek"
        elif _get_openai_key():
            provider_type = "openai"
        else:
            provider_type = "ollama"

    # Ollama — separate provider, different API
    if provider_type == "ollama":
        return OllamaProvider(**kwargs)

    # OpenAI-compatible providers (openai, deepseek, huggingface, or custom)
    if provider_type in ("openai", "deepseek", "huggingface"):
        # Resolve API key if not provided in kwargs
        if "api_key" not in kwargs and "api_token" not in kwargs:
            key_funcs = {
                "huggingface": _get_huggingface_token,
                "deepseek": _get_deepseek_key,
                "openai": _get_openai_key,
            }
            fn = key_funcs.get(provider_type)
            if fn:
                key = fn()
                if key:
                    kwargs["api_key"] = key

        return OpenAICompatibleProvider(provider_type=provider_type, **kwargs)

    # Custom provider name — try OpenAI-compatible with no key requirement
    return OpenAICompatibleProvider(
        provider_type=provider_type,
        api_key=kwargs.pop("api_key", None),
        model=kwargs.pop("model", None),
        base_url=kwargs.pop("base_url", None),
    )


__all__ = [
    "get_provider",
    "save_api_key",
    "get_api_key",
    "set_default_provider",
    "get_default_provider",
]
