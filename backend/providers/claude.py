"""Claude provider implementation."""

import httpx
from typing import List, Dict, Optional
from ..config import ANTHROPIC_API_KEY, PROVIDERS
from .base import ProviderClient


class ClaudeProvider(ProviderClient):
    """Anthropic Claude API client."""
    
    def __init__(self):
        self.api_key = ANTHROPIC_API_KEY
        self.endpoint = PROVIDERS["claude"]["endpoint"]
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
    
    async def chat(self, model: str, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Send chat completion request to Claude.
        
        Args:
            model: Model identifier (e.g., "claude-sonnet-4.5")
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            Response text or None if failed
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 1024,
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.endpoint,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                return data["content"][0]["text"]
                
        except Exception as e:
            print(f"Claude error for model {model}: {e}")
            return None
