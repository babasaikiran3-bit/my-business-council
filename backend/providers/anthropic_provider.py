"""Anthropic Claude provider integration."""

from typing import List, Dict
from anthropic import AsyncAnthropic
from .base import Provider, ProviderResponse


class AnthropicProvider(Provider):
    """Provider for Anthropic's Claude models."""

    def __init__(self, api_key: str):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
        """
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)

    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0
    ) -> ProviderResponse:
        """Query Claude API.

        Args:
            model: Claude model identifier (e.g., 'claude-opus-4-5-20251101')
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds

        Returns:
            ProviderResponse with normalized response
        """
        try:
            # Anthropic requires max_tokens parameter
            response = await self.client.messages.create(
                model=model,
                messages=messages,
                max_tokens=4096,
                timeout=timeout
            )

            # Extract content from response
            content = ""
            reasoning = None

            for block in response.content:
                if block.type == "text":
                    content = block.text
                # Future: handle thinking blocks if available
                # elif block.type == "thinking":
                #     reasoning = block.text

            return ProviderResponse(
                content=content,
                model=model,
                provider="anthropic",
                reasoning=reasoning,
                error=None
            )

        except Exception as e:
            # Return error response instead of raising
            error_msg = f"Anthropic API error: {str(e)}"
            print(error_msg)
            return ProviderResponse(
                content="",
                model=model,
                provider="anthropic",
                reasoning=None,
                error=error_msg
            )

    def get_provider_name(self) -> str:
        """Get provider name.

        Returns:
            'anthropic'
        """
        return "anthropic"
