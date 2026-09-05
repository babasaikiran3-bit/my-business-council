"""Provider abstraction for querying language models."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

LLMResponse = Dict[str, Any]


class LLMProvider(ABC):
    """Abstract provider contract used by council orchestration and future agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider name for observability."""

    @abstractmethod
    async def query_model(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Query a single model and return normalized response data."""

    async def query_models_parallel(
        self,
        models: List[str],
        messages: List[Dict[str, str]],
        timeout: Optional[float] = None,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Query multiple models in parallel using the provider's single-model query."""
        tasks = [self.query_model(model, messages, timeout=timeout) for model in models]
        responses = await asyncio.gather(*tasks)
        return {model: response for model, response in zip(models, responses)}


# Compatibility alias for existing imports.
BaseProvider = LLMProvider
