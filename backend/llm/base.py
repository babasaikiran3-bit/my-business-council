"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable, Awaitable


@dataclass
class LLMResponse:
    """Response from an LLM query.
    
    Attributes:
        content: The text content of the response.
        reasoning_details: Optional reasoning/chain-of-thought details (model-specific).
        raw_response: Optional raw response data from the provider.
    """
    content: Optional[str]
    reasoning_details: Optional[Any] = None
    raw_response: Optional[Dict[str, Any]] = None
    
    @property
    def success(self) -> bool:
        """Check if the response was successful (has content)."""
        return self.content is not None and len(self.content) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for storage/serialization."""
        return {
            "content": self.content,
            "reasoning_details": self.reasoning_details,
        }


# Type alias for progress callback
ProgressCallback = Callable[[str, Optional[LLMResponse], bool, int], Awaitable[None]]


class LLMProvider(ABC):
    """Abstract base class for LLM providers.
    
    This interface defines the contract for LLM providers, allowing
    the application to work with different backends (OpenRouter, direct API, etc.)
    without changing the core logic.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name (e.g., 'openrouter', 'anthropic')."""
        pass
    
    @property
    @abstractmethod
    def default_timeout(self) -> float:
        """Return the default timeout in seconds for API requests."""
        pass
    
    @abstractmethod
    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: Optional[float] = None,
    ) -> Optional[LLMResponse]:
        """Query a single model.
        
        Args:
            model: Model identifier (e.g., "openai/gpt-4o").
            messages: List of message dicts with 'role' and 'content'.
            timeout: Request timeout in seconds (uses default if None).
            
        Returns:
            LLMResponse if successful, None if failed.
        """
        pass
    
    @abstractmethod
    async def query_parallel(
        self,
        models: List[str],
        messages: List[Dict[str, str]],
        timeout: Optional[float] = None,
    ) -> Dict[str, Optional[LLMResponse]]:
        """Query multiple models in parallel.
        
        Args:
            models: List of model identifiers.
            messages: List of message dicts to send to each model.
            timeout: Request timeout in seconds per model (uses default if None).
            
        Returns:
            Dict mapping model identifier to LLMResponse (or None if failed).
        """
        pass
    
    @abstractmethod
    async def query_parallel_with_progress(
        self,
        models: List[str],
        messages: List[Dict[str, str]],
        on_model_complete: Optional[ProgressCallback] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Optional[LLMResponse]]:
        """Query multiple models in parallel with progress callbacks.
        
        Args:
            models: List of model identifiers.
            messages: List of message dicts to send to each model.
            on_model_complete: Callback(model, response, success, elapsed_ms) for each completion.
            timeout: Request timeout in seconds per model (uses default if None).
            
        Returns:
            Dict mapping model identifier to LLMResponse (or None if failed).
        """
        pass

