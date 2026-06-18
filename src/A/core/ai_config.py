"""Minimal provider configuration for A-kunpiloto.

Provides ``get_configured_provider`` used by :mod:`A_kunpiloto.cli`.

Full implementation lives in the ``feat/ai-config-abstraction`` branch.
This is a minimal shim so A-kunpiloto can import and function.
"""

from __future__ import annotations

from typing import Any

from A.core.ai import get_provider


def get_configured_provider(
    ref: str | None = None,
    **kwargs: Any,
) -> Any:
    """Resolve a provider reference to an ``LLMProvider`` instance.

    This is a thin shim over :func:`A.core.ai.get_provider` that
    accepts a provider name or ``None`` (falls back to "openai").

    Args:
        ref: Provider name (``"openai"``, ``"deepseek"``, ``"ollama"``)
            or ``None`` for auto-fallback.
        **kwargs: Passed to the provider constructor.

    Returns:
        ``LLMProvider`` instance.

    Raises:
        ValueError: If the provider type is unknown.
    """
    provider_type = ref or "openai"
    return get_provider(provider_type, **kwargs)
