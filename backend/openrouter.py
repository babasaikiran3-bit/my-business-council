"""OpenRouter API client for making LLM requests."""

import asyncio
import logging
from typing import List, Dict, Any, Optional

import httpx

from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL

logger = logging.getLogger(__name__)


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

    except httpx.TimeoutException:
        logger.error("Timeout querying model %s (%.0fs limit)", model, timeout)
        return None
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 401:
            logger.error("Authentication failed for model %s (401)", model)
        elif status == 429:
            logger.warning("Rate limited for model %s (429)", model)
        elif status >= 500:
            logger.error("Server error from OpenRouter for model %s (%d)", model, status)
        else:
            logger.error("HTTP error for model %s: %d", model, status)
        return None
    except (KeyError, IndexError) as e:
        logger.error("Unexpected response structure from model %s: %s", model, e)
        return None
    except Exception:
        logger.exception("Unexpected error querying model %s", model)
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
    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
