"""OpenRouter API provider implementation."""

import httpx
from typing import List, Dict, Any, Optional
from .base import Provider


class OpenRouterProvider(Provider):
    """Provider for OpenRouter API."""

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            base_url: Optional custom base URL (defaults to OpenRouter API)
        """
        super().__init__(
            base_url=base_url or self.DEFAULT_BASE_URL,
            api_key=api_key
        )

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "openrouter"

    def validate(self) -> bool:
        """
        Validate that the provider is properly configured.

        Returns:
            True if API key is present, False otherwise
        """
        return self.api_key is not None and len(self.api_key) > 0

    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Query a single model via OpenRouter API.

        Args:
            model: OpenRouter model identifier (e.g., "openai/gpt-4o")
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds
            **kwargs: Additional OpenRouter-specific parameters

        Returns:
            Response dict with 'content' and optional 'reasoning_details', or None if failed
        """
        if not self.validate():
            print(f"[{self.name}] Error: API key not configured")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            **kwargs  # Allow additional parameters like temperature, max_tokens, etc.
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.base_url,
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

        except httpx.HTTPStatusError as e:
            print(f"[{self.name}] HTTP error querying model {model}: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            print(f"[{self.name}] Error querying model {model}: {e}")
            return None
