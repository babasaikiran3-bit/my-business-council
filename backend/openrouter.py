"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


# Global connection pool for reuse across requests
_http_client: Optional[httpx.AsyncClient] = None


def _get_headers() -> Dict[str, str]:
    """Get standard headers for OpenRouter API."""
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


async def get_http_client() -> httpx.AsyncClient:
    """Get or create the shared HTTP client with connection pooling."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=300.0,  # 5 min total (for long responses)
                connect=10.0,   # 10s to establish connection
                read=30.0,      # 30s to wait for first byte / between chunks
                write=10.0,     # 10s to send request
                pool=10.0       # 10s to get connection from pool
            ),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0
            ),
            headers=_get_headers()
        )
    return _http_client


async def close_http_client():
    """Close the shared HTTP client (call on app shutdown)."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 60.0,
    max_tokens: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
        max_tokens: Maximum tokens to generate (optional, for limiting response)

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    payload = {
        "model": model,
        "messages": messages,
        "include_usage": True
    }
    
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    try:
        client = await get_http_client()
        response = await client.post(
            OPENROUTER_API_URL,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()

        data = response.json()
        message = data['choices'][0]['message']
        
        # Extract usage and cost information
        usage = data.get('usage', {})
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        
        # Calculate ESTIMATED cost from tokens (immediate)
        from .config import calculate_estimated_cost
        estimated_cost = calculate_estimated_cost(model, prompt_tokens, completion_tokens)
        
        # Extract generation ID for later cost polling
        generation_id = data.get('id', None)
        
        cost_info = {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': usage.get('total_tokens', 0),
            'cost': estimated_cost,
            'cost_status': 'estimated',
            'generation_id': generation_id
        }

        return {
            'content': message.get('content'),
            'reasoning_details': message.get('reasoning_details'),
            'usage': cost_info
        }

    except httpx.ReadTimeout:
        print(f"⚠️ TIMEOUT: Model {model} did not respond in time (read timeout) - skipping")
        return None
    except httpx.ConnectTimeout:
        print(f"⚠️ TIMEOUT: Could not connect to {model} (connect timeout) - skipping")
        return None
    except httpx.TimeoutException as e:
        print(f"⚠️ TIMEOUT: Model {model} timed out ({type(e).__name__}) - skipping")
        return None
    except httpx.HTTPStatusError as e:
        print(f"⚠️ HTTP ERROR: Model {model} returned {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"⚠️ ERROR: Model {model} failed: {type(e).__name__}: {e}")
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


async def fetch_actual_cost(generation_id: str) -> float:
    """
    Fetch actual cost from OpenRouter generation API.
    This polls the /generation endpoint to get the real cost after calculation.
    
    Args:
        generation_id: The generation ID from the chat completion response
    
    Returns:
        Actual cost in USD, or 0.0 if not available
    """
    if not generation_id:
        return 0.0
    
    try:
        client = await get_http_client()
        response = await client.get(
            f"https://openrouter.ai/api/v1/generation?id={generation_id}",
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            generation_data = data.get('data', {})
            actual_cost = generation_data.get('total_cost', 0.0)
            return float(actual_cost) if actual_cost else 0.0
        else:
            return 0.0
            
    except Exception as e:
        print(f"Error fetching actual cost for {generation_id}: {e}")
        return 0.0
