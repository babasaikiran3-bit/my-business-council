"""Provider factory for runtime provider selection."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from ..config import PROVIDER, validate_configuration
from .base import LLMProvider
from .ollama_provider import OllamaProvider
from .openrouter_provider import OpenRouterProvider


@lru_cache(maxsize=1)
def get_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """Return a configured provider instance."""
    selected = (provider_name or PROVIDER).strip().lower()
    if selected == "openrouter":
        selected = "api"
    if provider_name is None:
        validate_configuration()

    if selected == "api":
        return OpenRouterProvider()
    if selected == "ollama":
        return OllamaProvider()

    raise ValueError(
        f"Unsupported provider '{selected}'. Supported providers: api, ollama."
    )
