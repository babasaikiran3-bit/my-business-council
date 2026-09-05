"""Backward-compatible OpenRouter query helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .providers.openrouter_provider import OpenRouterProvider


_openrouter_provider = OpenRouterProvider()


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
) -> Optional[Dict[str, Any]]:
    """Query a single model via OpenRouter."""
    return await _openrouter_provider.query_model(model, messages, timeout=timeout)


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Query multiple models via OpenRouter in parallel."""
    return await _openrouter_provider.query_models_parallel(
        models, messages, timeout=timeout
    )
