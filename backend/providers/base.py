"""Base provider interface for LLM API abstraction."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class Provider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize provider.

        Args:
            base_url: Optional base URL for the API
            api_key: Optional API key for authentication
        """
        self.base_url = base_url
        self.api_key = api_key

    @abstractmethod
    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Query a single model.

        Args:
            model: Model identifier (without provider prefix)
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds
            **kwargs: Additional provider-specific parameters

        Returns:
            Response dict with 'content' and optional 'reasoning_details', or None if failed
        """
        pass

    async def query_batch(
        self,
        models: List[str],
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Query multiple models in parallel.

        Args:
            models: List of model identifiers (without provider prefix)
            messages: List of message dicts to send to each model
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict mapping model identifier to response dict (or None if failed)
        """
        import asyncio

        # Create tasks for all models
        tasks = [self.query(model, messages, **kwargs) for model in models]

        # Wait for all to complete
        responses = await asyncio.gather(*tasks)

        # Map models to their responses
        return {model: response for model, response in zip(models, responses)}

    @abstractmethod
    def validate(self) -> bool:
        """
        Validate that the provider is properly configured and reachable.

        Returns:
            True if provider is ready to use, False otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass
