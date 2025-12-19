"""OpenRouter API client for making LLM requests."""

import logging
import httpx
from typing import List, Dict, Any, Optional, Callable, Awaitable
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL

logger = logging.getLogger(__name__)


# Default timeout for OpenRouter API requests (8 minutes)
# Set to 8 minutes to accommodate slow models like openai/gpt-5.2-pro which can take 6+ minutes.
# This timeout applies to each individual model query.
DEFAULT_TIMEOUT = 480.0


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds (default: 480s / 8 minutes)

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

            content = message.get('content')
            if not content:
                logger.warning(f"[OPENROUTER] Model {model} returned empty content. Full message: {message}")

            return {
                'content': content,
                'reasoning_details': message.get('reasoning_details')
            }

    except httpx.HTTPStatusError as e:
        # Log specific HTTP status codes for better debugging
        status_code = e.response.status_code
        if status_code == 429:
            logger.error(f"[OPENROUTER] Rate limit exceeded for model {model}: {e}")
        elif status_code == 400:
            # Try to extract error details from response body
            try:
                error_body = e.response.json()
                error_message = error_body.get('error', {}).get('message', str(e))
                logger.error(f"[OPENROUTER] Bad request for model {model}: {error_message}")
            except Exception:
                logger.error(f"[OPENROUTER] Bad request for model {model}: {e}")
        elif status_code == 401:
            logger.error(f"[OPENROUTER] Authentication failed for model {model}: {e}")
        elif status_code == 402:
            logger.error(f"[OPENROUTER] Payment required (insufficient credits) for model {model}: {e}")
        elif status_code == 403:
            logger.error(f"[OPENROUTER] Access forbidden for model {model}: {e}")
        elif status_code == 404:
            logger.error(f"[OPENROUTER] Model not found: {model}. Check if model identifier is valid.")
        elif status_code >= 500:
            logger.error(f"[OPENROUTER] Server error ({status_code}) for model {model}: {e}")
        else:
            logger.error(f"[OPENROUTER] HTTP {status_code} error for model {model}: {e}")
        return None
    except httpx.TimeoutException as e:
        logger.error(f"[OPENROUTER] Request timeout for model {model}: {e}")
        return None
    except Exception as e:
        logger.error(f"[OPENROUTER] Unexpected error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        timeout: Request timeout in seconds per model (default: 480s / 8 minutes)

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages, timeout=timeout) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}


async def query_models_parallel_with_progress(
    models: List[str],
    messages: List[Dict[str, str]],
    on_model_complete: Optional[Callable[[str, Optional[Dict[str, Any]], bool, int], Awaitable[None]]] = None,
    timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel with progress callbacks.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        on_model_complete: Callback function(model, response, success, elapsed_ms) called when each model completes
        timeout: Request timeout in seconds per model (default: 480s / 8 minutes)

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio
    import time

    results = {}

    async def query_with_callback(model: str):
        start_time = time.time()
        response = await query_model(model, messages, timeout=timeout)
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
