"""Ollama provider for local LLM instances.

This module implements the LLM provider interface for Ollama, which runs
models locally. Ollama exposes an OpenAI-compatible API endpoint, making
integration straightforward.

Key Features:
    - Uses OpenAI-compatible /v1/chat/completions endpoint
    - No authentication required (local instance)
    - Supports Ollama model tags (e.g., llama3.1:8b, mistral:latest)
    - Graceful handling of connection errors and missing models
    - Parallel query support via asyncio
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import LLMProvider

# Configure logging
logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Provider implementation for local Ollama instances.

    Ollama is a tool for running LLMs locally. It exposes an OpenAI-compatible
    API endpoint, which this provider uses for communication.

    Attributes:
        base_url: Base URL for the Ollama instance (default: http://localhost:11434)

    Example:
        provider = OllamaProvider()
        result = await provider.query_model(
            "llama3.1:8b",
            [{"role": "user", "content": "Hello"}]
        )

    Common Error Scenarios:
        - Connection refused: Ollama service not running
        - 404 Not Found: Model not pulled/available locally
        - Timeout: Model loading or generation taking too long
        - Network errors: Local network issues
    """

    def __init__(self, base_url: str = 'http://localhost:11434'):
        """Initialize the Ollama provider.

        Args:
            base_url: Base URL for the Ollama instance. Should not include
                     trailing slash. Default is http://localhost:11434
        """
        self.base_url = base_url.rstrip('/')
        self.api_endpoint = f"{self.base_url}/v1/chat/completions"

    async def query_model(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0
    ) -> Optional[Dict[str, Any]]:
        """Query a single Ollama model with the given messages.

        This method sends a request to the local Ollama instance using the
        OpenAI-compatible chat completions endpoint.

        Args:
            model: Ollama model tag (e.g., "llama3.1:8b", "mistral:latest")
            messages: List of message dictionaries with 'role' and 'content' keys
            timeout: Maximum time in seconds to wait for response (default: 120.0)

        Returns:
            Dictionary with 'content' and 'reasoning_details' on success,
            None on any failure.

        Error Handling:
            - Connection errors → None (logs warning about Ollama not running)
            - 404 errors → None (logs warning about model not found)
            - Timeouts → None (logs warning about timeout)
            - Any other errors → None (logs error details)
        """
        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.api_endpoint,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                data = response.json()
                message = data['choices'][0]['message']

                return {
                    'content': message.get('content'),
                    'reasoning_details': None  # Ollama doesn't provide reasoning details
                }

        except httpx.ConnectError as e:
            logger.warning(
                f"Failed to connect to Ollama at {self.base_url}. "
                f"Is Ollama running? Error: {e}"
            )
            return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Model '{model}' not found in Ollama. "
                    f"Pull it with: ollama pull {model}"
                )
            else:
                logger.error(
                    f"HTTP error querying Ollama model {model}: "
                    f"Status {e.response.status_code}, {e}"
                )
            return None

        except httpx.TimeoutException as e:
            logger.warning(
                f"Timeout querying Ollama model {model} after {timeout}s. "
                f"Model may be loading or generation is slow. Error: {e}"
            )
            return None

        except Exception as e:
            logger.error(f"Unexpected error querying Ollama model {model}: {e}")
            return None

    async def query_models_parallel(
        self,
        models: List[str],
        messages: List[Dict[str, str]]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Query multiple Ollama models in parallel with the same messages.

        This method executes all queries concurrently to minimize total latency.
        Each model query is independent, and failures do not affect other queries.

        Args:
            models: List of Ollama model tags to query
            messages: List of message dictionaries to send to all models

        Returns:
            Dictionary mapping model tags to their responses.
            Successful queries return the standard response dict.
            Failed queries have None as their value.

        Example:
            results = await provider.query_models_parallel(
                ["llama3.1:8b", "mistral:latest"],
                [{"role": "user", "content": "Hello"}]
            )
            # results = {
            #     "llama3.1:8b": {"content": "Hi!", "reasoning_details": None},
            #     "mistral:latest": None  # This query failed
            # }

        Notes:
            - All queries execute concurrently using asyncio.gather
            - Individual model failures do not cause the entire operation to fail
            - The returned dict contains an entry for every model in the input list
        """
        # Create tasks for all models
        tasks = [self.query_model(model, messages) for model in models]

        # Wait for all to complete (return_exceptions=False means gather will
        # not raise, but our query_model already catches all exceptions)
        responses = await asyncio.gather(*tasks)

        # Map models to their responses
        return {model: response for model, response in zip(models, responses)}
