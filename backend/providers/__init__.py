"""LLM Provider abstractions for the council system.

This module provides a factory pattern for provider instantiation and intelligent
routing logic for both simple and mixed provider configurations.

Key Functions:
    - get_provider(provider_name): Get singleton provider instance
    - parse_model_spec(model_spec): Parse model spec into (provider, model) tuple
    - query_model(): Route single query to appropriate provider
    - query_models_parallel(): Route parallel queries with cross-provider support
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from backend.config import LLM_PROVIDER, OPENROUTER_API_KEY, OLLAMA_BASE_URL
from backend.providers.base import LLMProvider
from backend.providers.ollama import OllamaProvider
from backend.providers.openrouter import OpenRouterProvider


# Singleton provider instances
_provider_instances: Dict[str, LLMProvider] = {}


def get_provider(provider_name: str) -> LLMProvider:
    """Get a singleton instance of the specified provider.

    Args:
        provider_name: Provider name ("openrouter" or "ollama")

    Returns:
        LLMProvider instance for the specified provider

    Raises:
        ValueError: If provider_name is not "openrouter" or "ollama"

    Example:
        provider = get_provider("ollama")
        result = await provider.query_model("llama3.1:8b", messages)
    """
    if provider_name not in ["openrouter", "ollama"]:
        raise ValueError(
            f"Invalid provider name '{provider_name}'. Must be 'openrouter' or 'ollama'"
        )

    # Return existing instance if already created
    if provider_name in _provider_instances:
        return _provider_instances[provider_name]

    # Create new instance based on provider type
    if provider_name == "openrouter":
        if not OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY is required for openrouter provider. "
                "Set it in your .env file."
            )
        _provider_instances[provider_name] = OpenRouterProvider(
            api_key=OPENROUTER_API_KEY
        )
    else:  # ollama
        _provider_instances[provider_name] = OllamaProvider(
            base_url=OLLAMA_BASE_URL
        )

    return _provider_instances[provider_name]


def parse_model_spec(model_spec: str) -> Tuple[str, str]:
    """Parse a model specification into (provider, model) tuple.

    Handles two formats:
    1. Simple mode: "model_name" -> uses LLM_PROVIDER from config
    2. Mixed mode: "provider:model_name" -> explicit provider

    Args:
        model_spec: Model specification string
            - Simple: "llama3.1:8b" or "openai/gpt-4o"
            - Mixed: "ollama:llama3.1:8b" or "openrouter:openai/gpt-4o"

    Returns:
        Tuple of (provider_name, model_identifier)
            - provider_name: "openrouter" or "ollama"
            - model_identifier: The model name to pass to the provider

    Raises:
        ValueError: If mixed mode format is invalid or provider is unknown

    Examples:
        # Simple mode (uses LLM_PROVIDER from config)
        parse_model_spec("llama3.1:8b") -> ("ollama", "llama3.1:8b")
        parse_model_spec("openai/gpt-4o") -> ("openrouter", "openai/gpt-4o")

        # Mixed mode (explicit provider prefix)
        parse_model_spec("ollama:llama3.1:8b") -> ("ollama", "llama3.1:8b")
        parse_model_spec("openrouter:openai/gpt-4o") -> ("openrouter", "openai/gpt-4o")
    """
    # Check if this is mixed mode format (provider:model)
    if model_spec.startswith("ollama:"):
        return ("ollama", model_spec[7:])  # Remove "ollama:" prefix
    elif model_spec.startswith("openrouter:"):
        return ("openrouter", model_spec[11:])  # Remove "openrouter:" prefix

    # Simple mode - use global LLM_PROVIDER setting
    if LLM_PROVIDER == "mixed":
        raise ValueError(
            f"In mixed mode, model spec '{model_spec}' must include provider prefix "
            "(e.g., 'ollama:llama3.1:8b' or 'openrouter:openai/gpt-4o')"
        )

    return (LLM_PROVIDER, model_spec)


async def query_model(
    model_spec: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """Query a single model, routing to the appropriate provider.

    This is the main routing function for single model queries. It parses the
    model specification to determine the provider, gets the provider instance,
    and routes the query accordingly.

    Args:
        model_spec: Model specification string (see parse_model_spec for format)
        messages: List of message dicts with 'role' and 'content' keys
        timeout: Maximum time in seconds to wait for response (default: 120.0)

    Returns:
        Dictionary with 'content' and optional 'reasoning_details' on success,
        None on any failure (provider error, network error, timeout, etc.)

    Example:
        # Simple mode
        result = await query_model(
            "llama3.1:8b",
            [{"role": "user", "content": "Hello"}]
        )

        # Mixed mode
        result = await query_model(
            "openrouter:openai/gpt-4o",
            [{"role": "user", "content": "Hello"}]
        )

    Notes:
        - Maintains backward compatibility with original openrouter.py API
        - Returns same format as original implementation
        - Handles all errors gracefully, returns None on failure
    """
    try:
        provider_name, model_id = parse_model_spec(model_spec)
        provider = get_provider(provider_name)
        return await provider.query_model(model_id, messages, timeout)
    except ValueError as e:
        print(f"Error parsing model spec '{model_spec}': {e}")
        return None
    except Exception as e:
        print(f"Unexpected error querying model '{model_spec}': {e}")
        return None


async def query_models_parallel(
    model_specs: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Query multiple models in parallel, with cross-provider support.

    This function intelligently routes queries to their respective providers and
    executes them in parallel. For efficiency, it groups queries by provider to
    leverage each provider's native parallel execution capabilities.

    Args:
        model_specs: List of model specification strings (see parse_model_spec)
        messages: List of message dictionaries to send to all models

    Returns:
        Dictionary mapping model specifications to their responses.
        Successful queries return the standard response dict.
        Failed queries have None as their value.

    Example:
        # Mixed provider parallel queries
        results = await query_models_parallel(
            [
                "ollama:llama3.1:8b",
                "ollama:mistral:latest",
                "openrouter:openai/gpt-4o",
                "openrouter:anthropic/claude-3.5-sonnet"
            ],
            [{"role": "user", "content": "Hello"}]
        )
        # results = {
        #     "ollama:llama3.1:8b": {"content": "Hi!", "reasoning_details": None},
        #     "ollama:mistral:latest": None,  # Failed
        #     "openrouter:openai/gpt-4o": {"content": "Hello!", "reasoning_details": {...}},
        #     "openrouter:anthropic/claude-3.5-sonnet": {"content": "Hi!", "reasoning_details": None}
        # }

    Notes:
        - Groups queries by provider for efficient execution
        - All queries execute concurrently (both within and across providers)
        - Individual model failures do not affect other queries
        - Returns entry for every model in the input list
        - Maintains backward compatibility with original openrouter.py API
    """
    # Group models by provider for efficient parallel execution
    provider_groups: Dict[str, List[Tuple[str, str]]] = {}  # provider -> [(spec, model_id)]

    for model_spec in model_specs:
        try:
            provider_name, model_id = parse_model_spec(model_spec)
            if provider_name not in provider_groups:
                provider_groups[provider_name] = []
            provider_groups[provider_name].append((model_spec, model_id))
        except ValueError as e:
            print(f"Error parsing model spec '{model_spec}': {e}")
            # Add None entry for invalid specs
            provider_groups.setdefault("_invalid", []).append((model_spec, None))

    # Execute queries grouped by provider in parallel
    all_results = {}

    # Create tasks for each provider group
    provider_tasks = []
    for provider_name, specs_and_models in provider_groups.items():
        if provider_name == "_invalid":
            # Handle invalid specs - add None entries
            for model_spec, _ in specs_and_models:
                all_results[model_spec] = None
            continue

        # Get provider instance
        try:
            provider = get_provider(provider_name)
        except ValueError as e:
            print(f"Error getting provider '{provider_name}': {e}")
            # Mark all models for this provider as failed
            for model_spec, _ in specs_and_models:
                all_results[model_spec] = None
            continue

        # Extract just the model IDs for this provider
        model_ids = [model_id for _, model_id in specs_and_models]

        # Create task for this provider's batch query
        async def query_provider_batch(prov, model_ids_list, specs_list):
            """Helper to query a provider's models and map back to original specs."""
            results = await prov.query_models_parallel(model_ids_list, messages)
            # Map back from model_id to original model_spec
            return {
                spec: results[model_id]
                for spec, model_id in specs_list
            }

        provider_tasks.append(
            query_provider_batch(provider, model_ids, specs_and_models)
        )

    # Wait for all provider batches to complete
    if provider_tasks:
        provider_results = await asyncio.gather(*provider_tasks)

        # Merge all results
        for result_dict in provider_results:
            all_results.update(result_dict)

    # Ensure we have an entry for every input model spec
    for model_spec in model_specs:
        if model_spec not in all_results:
            all_results[model_spec] = None

    return all_results


# Export public API
__all__ = [
    'LLMProvider',
    'OllamaProvider',
    'OpenRouterProvider',
    'get_provider',
    'parse_model_spec',
    'query_model',
    'query_models_parallel',
]
