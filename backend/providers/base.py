"""Abstract base class for LLM providers.

This module defines the interface that all LLM provider implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    This class defines the interface contract that all LLM provider implementations
    must follow. Providers are responsible for communicating with their respective
    LLM APIs and handling errors gracefully.

    Interface Contract:
        All methods should handle errors internally and return None on failure
        rather than raising exceptions. This allows the system to continue
        operating even when individual providers or models fail.

    Return Format:
        All query methods must return a dictionary with the following structure:
        {
            "content": str,  # The main response text from the model
            "reasoning_details": Optional[Any]  # Optional reasoning trace or metadata
        }

        Returns None if the query fails for any reason (network error, API error,
        timeout, invalid model, etc.).

    Error Handling:
        Implementations should:
        - Catch all exceptions internally
        - Log errors appropriately
        - Return None on any failure
        - Never raise exceptions to callers
        - Implement appropriate timeout handling
    """

    @abstractmethod
    async def query_model(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0
    ) -> Optional[Dict[str, Any]]:
        """Query a single model with the given messages.

        Args:
            model: Model identifier (format depends on provider implementation)
            messages: List of message dictionaries with 'role' and 'content' keys
                     following the standard chat completion format:
                     [{"role": "user", "content": "..."},
                      {"role": "assistant", "content": "..."}, ...]
            timeout: Maximum time in seconds to wait for response (default: 120.0)

        Returns:
            Dictionary with 'content' and optional 'reasoning_details' on success,
            None on any failure (timeout, network error, API error, etc.)

        Example:
            result = await provider.query_model(
                "gpt-4",
                [{"role": "user", "content": "Hello"}]
            )
            if result:
                print(result["content"])
        """
        pass

    @abstractmethod
    async def query_models_parallel(
        self,
        models: List[str],
        messages: List[Dict[str, str]]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Query multiple models in parallel with the same messages.

        This method should execute all queries concurrently to minimize total
        latency. Each model query is independent and failures should not affect
        other queries.

        Args:
            models: List of model identifiers to query
            messages: List of message dictionaries to send to all models
                     (same format as query_model)

        Returns:
            Dictionary mapping model identifiers to their responses.
            Successful queries return the standard response dict.
            Failed queries have None as their value.

        Example:
            results = await provider.query_models_parallel(
                ["gpt-4", "claude-3"],
                [{"role": "user", "content": "Hello"}]
            )
            # results = {
            #     "gpt-4": {"content": "Hi there!", "reasoning_details": None},
            #     "claude-3": None  # This query failed
            # }

        Notes:
            - All queries execute concurrently using asyncio.gather or similar
            - Individual model failures should not cause the entire operation to fail
            - The returned dict should contain an entry for every model in the input list
        """
        pass
