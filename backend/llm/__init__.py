"""LLM provider abstraction layer.

This module provides an abstract interface for LLM providers, allowing
the application to work with different LLM backends (OpenRouter, direct API, etc.)
without changing the core logic.
"""

from .base import LLMProvider, LLMResponse
from .openrouter import OpenRouterProvider

# Default provider instance (singleton)
_default_provider: LLMProvider | None = None


def get_default_provider() -> LLMProvider:
    """Get the default LLM provider instance.
    
    Returns:
        The default LLMProvider (currently OpenRouterProvider).
    """
    global _default_provider
    if _default_provider is None:
        _default_provider = OpenRouterProvider()
    return _default_provider


def set_default_provider(provider: LLMProvider) -> None:
    """Set the default LLM provider instance.
    
    This is useful for testing or switching providers at runtime.
    
    Args:
        provider: The LLMProvider instance to use as default.
    """
    global _default_provider
    _default_provider = provider


__all__ = [
    "LLMProvider",
    "LLMResponse",
    "OpenRouterProvider",
    "get_default_provider",
    "set_default_provider",
]

