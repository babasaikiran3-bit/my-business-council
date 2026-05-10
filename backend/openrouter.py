"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional
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
        Response dict with 'content' and optional 'reasoning_details', or an
        'error' key if the request failed.
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

    except httpx.HTTPStatusError as e:
        error = _format_http_error(e)
        print(f"Error querying model {model}: {error}")
        return {"content": None, "error": error}
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        print(f"Error querying model {model}: {error}")
        return {"content": None, "error": error}


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
        Dict mapping model identifier to response dict. Failed requests include
        an 'error' key.
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}


def _format_http_error(error: httpx.HTTPStatusError) -> str:
    """Extract the useful OpenRouter error payload from an HTTP failure."""
    response = error.response
    status = response.status_code

    try:
        data = response.json()
    except ValueError:
        body = response.text.strip()
        if len(body) > 500:
            body = body[:497] + "..."
        return f"HTTP {status}: {body or response.reason_phrase}"

    detail = data.get("error", data)
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("code") or str(detail)
    else:
        message = str(detail)

    return f"HTTP {status}: {message}"
