"""Ollama API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional
from .config import OLLAMA_HOST, DEFAULT_TIMEOUT


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = None
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via Ollama API.

    Args:
        model: Ollama model identifier (e.g., "gemma3:latest")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds (defaults to DEFAULT_TIMEOUT from config)

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    
    url = f"http://{OLLAMA_HOST}/api/chat"
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['message']

            return {
                'content': message.get('content'),
                'reasoning_details': None  # Ollama API doesn't provide this
            }

    except httpx.ConnectError as e:
        print(f"Connection error querying model {model}: Cannot connect to Ollama at {OLLAMA_HOST}. Is Ollama running? Error: {e}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"HTTP error querying model {model}: Status {e.response.status_code}. Response: {e.response.text}")
        return None
    except httpx.TimeoutException as e:
        print(f"Timeout error querying model {model}: Request took longer than {timeout}s. Error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error querying model {model}: {type(e).__name__}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of Ollama model identifiers
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
