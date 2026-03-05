"""Provider abstraction layer for multiple LLM APIs."""

from .base import ProviderClient
from .openai import OpenAIProvider
from .gemini import GeminiProvider
from .claude import ClaudeProvider
from .cerebras import CerebrasProvider


def get_provider_client(provider: str) -> ProviderClient:
    """
    Get provider client instance.
    
    Args:
        provider: Provider name ('openai', 'gemini', 'claude', 'cerebras')
        
    Returns:
        ProviderClient instance
        
    Raises:
        ValueError: If provider is unknown
    """
    providers = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "cerebras": CerebrasProvider,
    }
    
    if provider not in providers:
        raise ValueError(f"Unknown provider: {provider}")
    
    return providers[provider]()
