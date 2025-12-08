"""Ollama API provider implementation."""

from typing import List, Dict, Any, Optional
from .base import Provider


class OllamaProvider(Provider):
    """Provider for Ollama local models."""

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama server URL (defaults to http://localhost:11434)
        """
        super().__init__(base_url=base_url or self.DEFAULT_BASE_URL)

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "ollama"

    def validate(self) -> bool:
        """
        Validate that the Ollama server is reachable.

        Returns:
            True if server is reachable, False otherwise
        """
        # For now, assume valid if base_url is set
        # Could add actual connectivity check with httpx if needed
        return self.base_url is not None

    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Query a single model via Ollama API.

        Args:
            model: Ollama model identifier (e.g., "llama2", "mistral")
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds
            **kwargs: Additional Ollama-specific parameters

        Returns:
            Response dict with 'content' and optional 'reasoning_details', or None if failed
        """
        try:
            from ollama import AsyncClient

            # Create client with custom host if specified
            client = AsyncClient(host=self.base_url)

            # Use the chat API for conversation-style interactions
            response = await client.chat(
                model=model,
                messages=messages,
                stream=False,
                options=kwargs.get('options', {})
            )

            # Extract content from Ollama response format
            # Ollama returns: {'model': ..., 'message': {'role': 'assistant', 'content': '...'}, ...}
            if 'message' in response and 'content' in response['message']:
                return {
                    'content': response['message']['content'],
                    'reasoning_details': None  # Ollama doesn't provide this
                }
            else:
                print(f"[{self.name}] Unexpected response format from model {model}: {response}")
                return None

        except ImportError:
            print(f"[{self.name}] Error: ollama package not installed. Run: pip install ollama")
            return None
        except Exception as e:
            print(f"[{self.name}] Error querying model {model}: {e}")
            return None
