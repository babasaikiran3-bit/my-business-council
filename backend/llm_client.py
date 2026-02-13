"""Unified LLM client using LiteLLM.

Supports multiple providers (OpenAI, Anthropic, Google Gemini, xAI, etc.)
with automatic fallback to OpenRouter when a direct API key isn't available.
"""

import asyncio
import litellm
from typing import List, Dict, Any, Optional
from .config import resolve_model

# Keep litellm quiet — only show warnings and errors
litellm.suppress_debug_info = True
litellm.set_verbose = False


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
) -> Optional[Dict[str, Any]]:
    """Query a single model via LiteLLM (routes to the appropriate provider).

    Args:
        model: Model identifier in litellm format (e.g. "openai/gpt-5.1",
               "gemini/gemini-3-pro-preview", "anthropic/claude-sonnet-4.5").
        messages: List of message dicts with 'role' and 'content'.
        timeout: Request timeout in seconds.

    Returns:
        Dict with 'content' and optional 'reasoning_details', or None on failure.
    """
    try:
        resolved = resolve_model(model)

        response = await litellm.acompletion(
            model=resolved,
            messages=messages,
            timeout=timeout,
        )

        message = response.choices[0].message

        return {
            "content": message.content,
            "reasoning_details": getattr(message, "reasoning_content", None),
        }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Query multiple models in parallel.

    Args:
        models: List of model identifiers (litellm format).
        messages: List of message dicts to send to each model.

    Returns:
        Dict mapping model identifier to response dict (or None if failed).
    """
    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)
    return {model: response for model, response in zip(models, responses)}
