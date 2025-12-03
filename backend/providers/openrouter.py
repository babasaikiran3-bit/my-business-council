"""OpenRouter LLM provider implementation.

This module implements the LLMProvider interface for OpenRouter API,
preserving the exact behavior of the original openrouter.py implementation.
"""

import asyncio
import httpx
from typing import Any, Dict, List, Optional

from backend.providers.base import LLMProvider


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider implementation.

    This provider communicates with OpenRouter's API to query various LLM models.
    It implements graceful degradation - failed requests return None without raising
    exceptions, allowing the system to continue with successful responses.

    Args:
        api_key: OpenRouter API key for authentication
        api_url: OpenRouter API endpoint URL (default: https://openrouter.ai/api/v1/chat/completions)

    Example:
        provider = OpenRouterProvider(api_key="sk-...")
        result = await provider.query_model(
            "openai/gpt-4o",
            [{"role": "user", "content": "Hello"}]
        )
    """

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://openrouter.ai/api/v1/chat/completions"
    ):
        """Initialize the OpenRouter provider.

        Args:
            api_key: OpenRouter API key for authentication
            api_url: OpenRouter API endpoint URL (default: https://openrouter.ai/api/v1/chat/completions)
        """
        self.api_key = api_key
        self.api_url = api_url

    async def query_model(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0
    ) -> Optional[Dict[str, Any]]:
        """Query a single model via OpenRouter API.

        Args:
            model: OpenRouter model identifier (e.g., "openai/gpt-4o")
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds (default: 120.0)

        Returns:
            Response dict with 'content' and optional 'reasoning_details', or None if failed

        Notes:
            - Handles all errors internally, returns None on failure
            - Preserves exact behavior from original implementation
            - Prints error messages to console for debugging
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                data = response.json()
                message = data['choices'][0]['message']

                return {
                    'content': message.get('content'),
                    'reasoning_details': message.get('reasoning_details')
                }

        except Exception as e:
            print(f"Error querying model {model}: {e}")
            return None

    async def query_models_parallel(
        self,
        models: List[str],
        messages: List[Dict[str, str]]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Query multiple models in parallel.

        Args:
            models: List of OpenRouter model identifiers
            messages: List of message dicts to send to each model

        Returns:
            Dict mapping model identifier to response dict (or None if failed)

        Notes:
            - Uses asyncio.gather for concurrent execution
            - Individual model failures don't affect other queries
            - Returns entry for every model in input list
        """
        # Create tasks for all models
        tasks = [self.query_model(model, messages) for model in models]

        # Wait for all to complete
        responses = await asyncio.gather(*tasks)

        # Map models to their responses
        return {model: response for model, response in zip(models, responses)}
