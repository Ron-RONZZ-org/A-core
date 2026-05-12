"""LLM provider factory and API key management for A-core.

Concrete provider implementations live in A.core.providers.

This module provides only:
- Provider factory (get_provider)
- Keyring-based API key storage (save_api_key, get_api_key)

Default provider fallback and auto-detection are managed by A-agento
(A_agento.provider_state). Users of A-agento should use
A_agento.commands._helpers.get_provider_or_exit() or
A_agento.provider_state.get_provider_with_fallback() for
auto-selection.

Usage:
    from A.core.ai import get_provider

    provider = get_provider("deepseek")
    result = provider.generate("Summarize: The meeting is at 3pm tomorrow.")
"""

from __future__ import annotations

from typing import Any

from A.core import keyring as _keyring
from A.core.providers import (
    LLMProvider,
    OpenAICompatibleProvider,
    OllamaProvider,
)


# ============================================================================
# API key management (system keyring)
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
# Provider factory
# ============================================================================


def get_provider(provider_type: str, **kwargs: Any) -> LLMProvider:
    """Factory: create an LLM provider by type.

    Provider must be explicitly specified. Default fallback is managed
    by A-agento's A_agento.provider_state module.

    Args:
        provider_type: "huggingface", "deepseek", "openai", "ollama",
                       or any name for an OpenAI-compatible endpoint.
        **kwargs: Overrides such as model, base_url, api_key.

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider type is unknown
    """
    if provider_type == "ollama":
        return OllamaProvider(**kwargs)

    # OpenAI-compatible providers (openai, deepseek, huggingface, custom).
    # API key is resolved automatically by OpenAICompatibleProvider on
    # first use (env -> .env -> keyring). Callers can override with
    # explicit api_key kwarg.
    return OpenAICompatibleProvider(provider_type=provider_type, **kwargs)


__all__ = [
    "get_provider",
    "save_api_key",
    "get_api_key",
]
