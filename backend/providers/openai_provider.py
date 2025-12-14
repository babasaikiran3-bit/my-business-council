"""OpenAI GPT provider integration."""

from typing import List, Dict
from openai import AsyncOpenAI
from .base import Provider, ProviderResponse


class OpenAIProvider(Provider):
    """Provider for OpenAI's GPT models."""

    def __init__(self, api_key: str):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
        """
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)

    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0
    ) -> ProviderResponse:
        """Query OpenAI API.

        Args:
            model: OpenAI model identifier (e.g., 'gpt-5.2', 'gpt-5-mini')
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds

        Returns:
            ProviderResponse with normalized response
        """
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=timeout
            )

            # Extract content from response
            content = response.choices[0].message.content or ""

            # Check for reasoning content (o-series models)
            reasoning = None
            if hasattr(response.choices[0].message, 'reasoning_content'):
                reasoning = response.choices[0].message.reasoning_content

            return ProviderResponse(
                content=content,
                model=model,
                provider="openai",
                reasoning=reasoning,
                error=None
            )

        except Exception as e:
            # Return error response instead of raising
            error_msg = f"OpenAI API error: {str(e)}"
            print(error_msg)
            return ProviderResponse(
                content="",
                model=model,
                provider="openai",
                reasoning=None,
                error=error_msg
            )

    def get_provider_name(self) -> str:
        """Get provider name.

        Returns:
            'openai'
        """
        return "openai"
