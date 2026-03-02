"""Provider dispatcher for LLM Council."""

import asyncio
import importlib
from typing import List, Dict, Any, Optional

from ..config import get_model_name

# Cache for loaded provider modules
_provider_cache: Dict[str, Any] = {}


def _get_provider(name: str):
    """Lazy-load and cache a provider module."""
    if name not in _provider_cache:
        try:
            _provider_cache[name] = importlib.import_module(f".{name}", package=__package__)
        except ImportError as e:
            raise ImportError(f"Provider '{name}' not found or has missing dependencies: {e}")
    return _provider_cache[name]


async def query_model(
    model_config,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model, routing to the correct provider.

    Args:
        model_config: Dict with 'provider' and 'model' keys, or a plain string (legacy)
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    if isinstance(model_config, str):
        # Legacy: plain string treated as openrouter model
        provider_name = "openrouter"
        model = model_config
    else:
        provider_name = model_config["provider"]
        model = model_config["model"]

    provider = _get_provider(provider_name)
    return await provider.query_model(model, messages, timeout)


async def query_models_parallel(
    model_configs: list,
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        model_configs: List of model config dicts (or plain strings for legacy)
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping display model name to response dict (or None if failed)
    """
    tasks = [query_model(cfg, messages) for cfg in model_configs]
    responses = await asyncio.gather(*tasks)

    return {
        get_model_name(cfg): response
        for cfg, response in zip(model_configs, responses)
    }


def validate_providers(model_configs: list) -> Dict[str, str]:
    """
    Check which providers have their required API keys configured.
    Returns dict mapping provider name to status string.
    """
    from ..config import (
        OPENROUTER_API_KEY, OPENAI_API_KEY, CURSOR_API_KEY,
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
    )

    key_checks = {
        "openrouter": bool(OPENROUTER_API_KEY),
        "openai_direct": bool(OPENAI_API_KEY),
        "bedrock": bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY),
        "cursor_agent": bool(CURSOR_API_KEY),
    }

    # Only report on providers actually in use
    used_providers = set()
    for cfg in model_configs:
        if isinstance(cfg, str):
            used_providers.add("openrouter")
        else:
            used_providers.add(cfg["provider"])

    results = {}
    for provider in used_providers:
        if provider in key_checks:
            results[provider] = "OK" if key_checks[provider] else "MISSING KEY"
        else:
            results[provider] = "UNKNOWN"

    return results
