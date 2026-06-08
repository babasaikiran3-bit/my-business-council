"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


def _extract_error_message(response: httpx.Response) -> str:
    """Extract a human-readable error from an OpenRouter API response."""
    try:
        data = response.json()
        error = data.get("error", {})
        if isinstance(error, dict):
            return error.get("message", response.text)
        return str(error) or response.text
    except Exception:
        return response.text or f"HTTP {response.status_code}"


def _is_successful_response(response: Optional[Dict[str, Any]]) -> bool:
    """Return True if the response contains usable model content."""
    return bool(response and response.get("content") and not response.get("error"))


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
        Response dict with 'content' and optional 'reasoning_details' on success,
        or dict with 'error' and optional 'status_code' on failure, or None if
        the API key is missing.
    """
    if not OPENROUTER_API_KEY:
        return {
            "error": "OPENROUTER_API_KEY is not set. Add it to your .env file.",
            "status_code": None,
        }

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
                return {
                    "error": f"Model {model} returned an empty response.",
                    "status_code": response.status_code,
                }

            return {
                'content': content,
                'reasoning_details': message.get('reasoning_details')
            }

    except httpx.HTTPStatusError as e:
        error_message = _extract_error_message(e.response)
        print(f"Error querying model {model}: {error_message}")
        return {
            "error": error_message,
            "status_code": e.response.status_code,
        }
    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return {
            "error": str(e),
            "status_code": None,
        }


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
