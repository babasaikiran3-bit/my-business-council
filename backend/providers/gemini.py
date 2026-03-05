"""Gemini provider implementation."""

import httpx
from typing import List, Dict, Optional
from ..config import GEMINI_API_KEY, PROVIDERS
from .base import ProviderClient


class GeminiProvider(ProviderClient):
    """Google Gemini API client."""
    
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.endpoint_template = PROVIDERS["gemini"]["endpoint"]
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured")
    
    async def chat(self, model: str, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Send chat completion request to Gemini.
        
        Args:
            model: Model identifier (e.g., "models/gemini-2.5-flash")
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            Response text or None if failed
        """
        # Build endpoint with model name
        endpoint = self.endpoint_template.format(model=model)
        endpoint = f"{endpoint}?key={self.api_key}"
        
        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        
        payload = {
            "contents": contents
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    endpoint,
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
                
        except Exception as e:
            print(f"Gemini error for model {model}: {e}")
            return None
