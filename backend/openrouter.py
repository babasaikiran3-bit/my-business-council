"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL
from .logging_config import get_logger

logger = get_logger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError)),
    before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    reraise=True,
)
async def _query_model_with_retry(
    model: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: float
) -> Dict[str, Any]:
    """
    Internal function that performs the actual API call with retry logic.

    This is separated to allow tenacity to retry only network-related errors
    while letting other errors (like HTTP 4xx) fail immediately.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API with automatic retries.

    Automatically retries on:
    - Network errors (with exponential backoff: 2s, 4s, 8s)
    - Timeout errors
    - Connection errors

    Does NOT retry on:
    - HTTP 4xx errors (client errors - bad request, auth, etc.)
    - HTTP 5xx errors (server errors - will fail fast)

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
        data = await _query_model_with_retry(model, headers, payload, timeout)
        message = data['choices'][0]['message']

        logger.debug(
            "model_query_success",
            model=model,
            prompt_length=len(messages[0].get('content', '')) if messages else 0,
            response_length=len(message.get('content', ''))
        )

        return {
            'content': message.get('content'),
            'reasoning_details': message.get('reasoning_details')
        }

    except httpx.TimeoutException as e:
        logger.warning(
            "model_query_timeout",
            model=model,
            timeout=timeout,
            error=str(e)
        )
        return None
    except httpx.HTTPStatusError as e:
        status_code = None
        if hasattr(e, 'response') and e.response is not None:
            status_code = e.response.status_code
        logger.error(
            "model_query_http_error",
            model=model,
            status_code=status_code,
            error=str(e)
        )
        return None
    except Exception as e:
        logger.error(
            "model_query_failed",
            model=model,
            error_type=type(e).__name__,
            error=str(e)
        )
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
