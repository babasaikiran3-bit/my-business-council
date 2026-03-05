"""OpenAI provider implementation."""

import httpx
from typing import List, Dict, Optional
from ..config import OPENAI_API_KEY, PROVIDERS
from .base import ProviderClient


class OpenAIProvider(ProviderClient):
    """OpenAI API client."""
    
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.endpoint = PROVIDERS["openai"]["endpoint"]
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured")
    
    async def chat(self, model: str, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Send chat completion request to OpenAI.
        
        Args:
            model: Model identifier (e.g., "gpt-4o")
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            Response text or None if failed
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": messages,
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
                return data["choices"][0]["message"]["content"]
                
        except Exception as e:
            print(f"OpenAI error for model {model}: {e}")
            return None
