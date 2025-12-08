"""LMStudio API provider implementation."""

import httpx
from typing import List, Dict, Any, Optional
from .base import Provider


class LMStudioProvider(Provider):
    """Provider for LMStudio local models (OpenAI-compatible API)."""

    DEFAULT_BASE_URL = "http://localhost:1234/v1/chat/completions"

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize LMStudio provider.

        Args:
            base_url: LMStudio server URL (defaults to http://localhost:1234/v1/chat/completions)
        """
        super().__init__(base_url=base_url or self.DEFAULT_BASE_URL)

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "lmstudio"

    def validate(self) -> bool:
        """
        Validate that the provider is properly configured.

        Returns:
            True if base_url is set, False otherwise
        """
        return self.base_url is not None

    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Query a single model via LMStudio API (OpenAI-compatible).

        Args:
            model: Model identifier loaded in LMStudio
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Response dict with 'content' and optional 'reasoning_details', or None if failed
        """
        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            **kwargs  # Allow additional parameters
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

                # LMStudio uses OpenAI-compatible response format
                message = data['choices'][0]['message']

                return {
                    'content': message.get('content'),
                    'reasoning_details': message.get('reasoning_details')
                }

        except httpx.HTTPStatusError as e:
            print(f"[{self.name}] HTTP error querying model {model}: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.ConnectError:
            print(f"[{self.name}] Connection error: Is LMStudio running at {self.base_url}?")
            return None
        except Exception as e:
            print(f"[{self.name}] Error querying model {model}: {e}")
            return None
