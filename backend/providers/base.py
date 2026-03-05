"""Base provider interface."""

from typing import List, Dict, Optional


class ProviderClient:
    """Abstract base class for LLM provider clients."""
    
    async def chat(self, model: str, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Send chat completion request to provider.
        
        Args:
            model: Model identifier
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            Response text or None if failed
        """
        raise NotImplementedError
