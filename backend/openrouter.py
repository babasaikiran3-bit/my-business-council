"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional, Callable, Awaitable
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details')
            }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}


async def query_models_parallel_with_progress(
    models: List[str],
    messages: List[Dict[str, str]],
    on_model_complete: Optional[Callable[[str, Optional[Dict[str, Any]], bool, int], Awaitable[None]]] = None
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel with progress callbacks.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        on_model_complete: Callback function(model, response, success, elapsed_ms) called when each model completes

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio
    import time

    results = {}

    async def query_with_callback(model: str):
        start_time = time.time()
        response = await query_model(model, messages)
        elapsed_ms = int((time.time() - start_time) * 1000)  # Convert to milliseconds
        success = response is not None
        if on_model_complete:
            await on_model_complete(model, response, success, elapsed_ms)
        return model, response

    # Create tasks for all models
    tasks = [query_with_callback(model) for model in models]

    # Wait for all to complete (as_completed gives us results as they finish)
    for coro in asyncio.as_completed(tasks):
        model, response = await coro
        results[model] = response

    return results
