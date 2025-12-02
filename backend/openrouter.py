"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional, Tuple
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


class OpenRouterError(Exception):
    """Custom exception for OpenRouter API errors with detailed messages."""
    def __init__(self, message: str, model: str = None, status_code: int = None):
        self.message = message
        self.model = model
        self.status_code = status_code
        super().__init__(self.message)


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
            
            # Handle HTTP errors with detailed messages
            if response.status_code != 200:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = error_data.get('error', {}).get('message', str(error_data))
                except:
                    error_detail = response.text[:200] if response.text else "Unknown error"
                
                error_msg = f"HTTP {response.status_code}: {error_detail}"
                raise OpenRouterError(error_msg, model=model, status_code=response.status_code)

            data = response.json()
            
            # Validate response structure
            if 'choices' not in data or len(data['choices']) == 0:
                raise OpenRouterError("Invalid API response: no choices returned", model=model)
            
            message = data['choices'][0].get('message', {})

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details'),
                'error': None
            }

    except OpenRouterError:
        raise  # Re-raise our custom errors
    except httpx.TimeoutException:
        raise OpenRouterError(f"Request timed out after {timeout} seconds", model=model)
    except httpx.ConnectError:
        raise OpenRouterError("Failed to connect to OpenRouter API. Check your internet connection.", model=model)
    except Exception as e:
        raise OpenRouterError(f"Unexpected error: {str(e)}", model=model)


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    return_exceptions: bool = True
) -> Tuple[Dict[str, Optional[Dict[str, Any]]], List[str]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        return_exceptions: If True, capture exceptions instead of raising

    Returns:
        Tuple of (responses dict, list of error messages)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete, capturing exceptions
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Map models to their responses, collecting errors
    result = {}
    errors = []
    
    for model, response in zip(models, responses):
        if isinstance(response, OpenRouterError):
            errors.append(f"{model}: {response.message}")
            result[model] = None
        elif isinstance(response, Exception):
            errors.append(f"{model}: {str(response)}")
            result[model] = None
        else:
            result[model] = response
    
    return result, errors
