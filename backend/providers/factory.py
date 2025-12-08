"""Provider factory for routing model requests to appropriate providers."""

from typing import Dict, List, Any, Optional, Tuple
from .base import Provider
from .openrouter import OpenRouterProvider
from .ollama import OllamaProvider
from .lmstudio import LMStudioProvider


class ProviderFactory:
    """
    Factory class for managing and routing to different LLM providers.

    Supports model identifiers in two formats:
    1. Prefixed: "provider:model" (e.g., "ollama:llama2", "openrouter:gpt-4")
    2. Simple: "model" (uses default_provider)
    """

    def __init__(
        self,
        default_provider: str = "openrouter",
        openrouter_api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        lmstudio_base_url: Optional[str] = None
    ):
        """
        Initialize the provider factory.

        Args:
            default_provider: Default provider name for unprefixed model identifiers
            openrouter_api_key: API key for OpenRouter
            ollama_base_url: Base URL for Ollama server
            lmstudio_base_url: Base URL for LMStudio server
        """
        self.default_provider = default_provider
        self._providers: Dict[str, Provider] = {}

        # Initialize providers
        self._providers['openrouter'] = OpenRouterProvider(
            api_key=openrouter_api_key
        )
        self._providers['ollama'] = OllamaProvider(
            base_url=ollama_base_url
        )
        self._providers['lmstudio'] = LMStudioProvider(
            base_url=lmstudio_base_url
        )

    def parse_model_identifier(self, model_identifier: str) -> Tuple[str, str]:
        """
        Parse a model identifier into (provider_name, model_name).

        Args:
            model_identifier: Either "provider:model" or "model"

        Returns:
            Tuple of (provider_name, model_name)

        Examples:
            "ollama:llama2" -> ("ollama", "llama2")
            "openrouter:gpt-4" -> ("openrouter", "gpt-4")
            "gpt-4" -> ("openrouter", "gpt-4")  # uses default_provider
        """
        if ':' in model_identifier:
            # Prefixed format: "provider:model"
            parts = model_identifier.split(':', 1)
            provider_name = parts[0].lower()
            model_name = parts[1]
            return provider_name, model_name
        else:
            # Simple format: use default provider
            return self.default_provider, model_identifier

    def get_provider(self, provider_name: str) -> Optional[Provider]:
        """
        Get a provider instance by name.

        Args:
            provider_name: Name of the provider ("openrouter", "ollama", "lmstudio")

        Returns:
            Provider instance or None if not found
        """
        return self._providers.get(provider_name.lower())

    async def query_model(
        self,
        model_identifier: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Query a single model using the appropriate provider.

        Args:
            model_identifier: Model identifier (e.g., "ollama:llama2", "gpt-4")
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds
            **kwargs: Additional provider-specific parameters

        Returns:
            Response dict with 'content' and optional 'reasoning_details', or None if failed
        """
        provider_name, model_name = self.parse_model_identifier(model_identifier)
        provider = self.get_provider(provider_name)

        if provider is None:
            print(f"[ProviderFactory] Error: Unknown provider '{provider_name}' in model identifier '{model_identifier}'")
            return None

        if not provider.validate():
            print(f"[ProviderFactory] Warning: Provider '{provider_name}' is not properly configured")
            return None

        return await provider.query(model_name, messages, timeout, **kwargs)

    async def query_models_parallel(
        self,
        model_identifiers: List[str],
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Query multiple models in parallel, automatically routing to appropriate providers.

        Args:
            model_identifiers: List of model identifiers (can be mixed providers)
            messages: List of message dicts to send to each model
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict mapping original model identifier to response dict (or None if failed)

        Example:
            >>> factory.query_models_parallel([
            ...     "ollama:llama2",
            ...     "openrouter:gpt-4",
            ...     "lmstudio:mistral"
            ... ], messages)
        """
        import asyncio

        # Group models by provider for batch optimization
        provider_groups: Dict[str, List[Tuple[str, str]]] = {}
        for model_id in model_identifiers:
            provider_name, model_name = self.parse_model_identifier(model_id)
            if provider_name not in provider_groups:
                provider_groups[provider_name] = []
            provider_groups[provider_name].append((model_id, model_name))

        # Query each provider's models in batch
        all_tasks = []
        task_to_model_id = {}

        for provider_name, models in provider_groups.items():
            provider = self.get_provider(provider_name)
            if provider is None or not provider.validate():
                # Skip invalid providers, return None for their models
                for model_id, _ in models:
                    task_to_model_id[model_id] = None
                continue

            # Use provider's batch query if available, otherwise query individually
            model_names = [model_name for _, model_name in models]
            task = provider.query_batch(model_names, messages, **kwargs)
            all_tasks.append((provider_name, models, task))

        # Execute all provider batches in parallel
        results = {}
        if all_tasks:
            batch_results = await asyncio.gather(*[task for _, _, task in all_tasks])

            # Map results back to original model identifiers
            for (provider_name, models, _), batch_result in zip(all_tasks, batch_results):
                for model_id, model_name in models:
                    results[model_id] = batch_result.get(model_name)

        # Add None results for invalid providers
        for model_id, response in task_to_model_id.items():
            if response is None:
                results[model_id] = None

        return results

    def validate_all(self) -> Dict[str, bool]:
        """
        Validate all providers.

        Returns:
            Dict mapping provider name to validation status
        """
        return {
            name: provider.validate()
            for name, provider in self._providers.items()
        }

    def get_available_providers(self) -> List[str]:
        """
        Get list of available (validated) provider names.

        Returns:
            List of provider names that are properly configured
        """
        return [
            name for name, provider in self._providers.items()
            if provider.validate()
        ]
