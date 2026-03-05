"""Cerebras provider implementation."""

import httpx
from typing import List, Dict, Optional
from ..config import CEREBRAS_API_KEY, PROVIDERS
from .base import ProviderClient


class CerebrasProvider(ProviderClient):
    """Cerebras API client (OpenAI-compatible)."""
    
    def __init__(self):
        self.api_key = CEREBRAS_API_KEY
        self.endpoint = PROVIDERS["cerebras"]["endpoint"]
        
        if not self.api_key:
            raise ValueError("CEREBRAS_API_KEY not configured")
    
    async def chat(self, model: str, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Send chat completion request to Cerebras.
        
        Args:
            model: Model identifier (e.g., "llama3.1-8b")
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
            print(f"Cerebras error for model {model}: {e}")
            return None
