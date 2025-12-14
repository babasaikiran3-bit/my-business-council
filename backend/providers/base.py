"""Base provider interface for LLM integrations."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ProviderResponse:
    """Normalized response format from all providers."""
    content: str
    model: str
    provider: str
    reasoning: Optional[str] = None
    error: Optional[str] = None


class Provider(ABC):
    """Abstract base class for LLM provider integrations."""

    def __init__(self, api_key: str):
        """Initialize provider with API key.

        Args:
            api_key: API key for the provider
        """
        self.api_key = api_key

    @abstractmethod
    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0
    ) -> ProviderResponse:
        """Query the provider's API and return normalized response.

        Args:
            model: Model identifier for this provider
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds

        Returns:
            ProviderResponse with normalized response data
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name (e.g., 'anthropic', 'openai', 'google').

        Returns:
            Provider name string
        """
        pass
