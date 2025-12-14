"""Unified LLM client that routes requests to appropriate providers."""

import asyncio
from typing import List, Dict, Optional
from .providers import AnthropicProvider, OpenAIProvider, GoogleProvider, ProviderResponse
from .config import (
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    GOOGLE_API_KEY,
    MODEL_PROVIDER_MAP
)


class LLMClient:
    """Unified client for querying multiple LLM providers."""

    def __init__(self):
        """Initialize all provider clients."""
        self.providers = {}

        # Initialize each provider if API key is available
        if ANTHROPIC_API_KEY:
            self.providers['anthropic'] = AnthropicProvider(ANTHROPIC_API_KEY)

        if OPENAI_API_KEY:
            self.providers['openai'] = OpenAIProvider(OPENAI_API_KEY)

        if GOOGLE_API_KEY:
            self.providers['google'] = GoogleProvider(GOOGLE_API_KEY)

    def _get_provider_for_model(self, model: str) -> Optional[str]:
        """Get provider name for a given model.

        Args:
            model: Model identifier

        Returns:
            Provider name ('anthropic', 'openai', 'google') or None if not found
        """
        return MODEL_PROVIDER_MAP.get(model)

    async def query_model(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0
    ) -> Optional[Dict[str, any]]:
        """Query a single model via its provider.

        Args:
            model: Model identifier (e.g., 'claude-opus-4-5-20251101')
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds

        Returns:
            Response dict with 'content' and optional 'reasoning_details', or None if failed
        """
        # Get provider for this model
        provider_name = self._get_provider_for_model(model)
        if not provider_name:
            print(f"Error: No provider mapped for model '{model}'")
            return None

        # Get provider instance
        provider = self.providers.get(provider_name)
        if not provider:
            print(f"Error: Provider '{provider_name}' not initialized (check API key)")
            return None

        # Query the provider
        response = await provider.query(model, messages, timeout)

        # Check for errors
        if response.error:
            print(f"Error querying {model}: {response.error}")
            return None

        # Return in OpenRouter-compatible format for backwards compatibility
        return {
            'content': response.content,
            'reasoning_details': response.reasoning
        }

    async def query_models_parallel(
        self,
        models: List[str],
        messages: List[Dict[str, str]]
    ) -> Dict[str, Optional[Dict[str, any]]]:
        """Query multiple models in parallel.

        Args:
            models: List of model identifiers
            messages: List of message dicts to send to each model

        Returns:
            Dict mapping model identifier to response dict (or None if failed)
        """
        # Create tasks for all models
        tasks = [self.query_model(model, messages) for model in models]

        # Wait for all to complete
        responses = await asyncio.gather(*tasks)

        # Map models to their responses
        return {model: response for model, response in zip(models, responses)}


# Global client instance
_client = None


def get_client() -> LLMClient:
    """Get or create the global LLM client instance.

    Returns:
        LLMClient instance
    """
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


# Backwards-compatible interface for existing code
async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, any]]:
    """Query a single model (backwards compatible).

    Args:
        model: Model identifier
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    client = get_client()
    return await client.query_model(model, messages, timeout)


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, any]]]:
    """Query multiple models in parallel (backwards compatible).

    Args:
        models: List of model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    client = get_client()
    return await client.query_models_parallel(models, messages)
