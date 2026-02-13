"""OpenRouter API client for making LLM requests."""

import httpx
import json
import asyncio
import random
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL

# Constants for rate limiting
MAX_RETRIES = 3
BACKOFF_FACTOR = 2
CONCURRENCY_LIMIT = 2

# Global semaphore for rate limiting (lazy loaded)
_semaphore = None

def get_semaphore():
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    return _semaphore


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

    semaphore = get_semaphore()
    
    async with semaphore:
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        OPENROUTER_API_URL,
                        headers=headers,
                        json=payload
                    )
                    
                    if response.status_code == 429:
                        # Rate limited
                        if attempt < MAX_RETRIES:
                            wait_time = (BACKOFF_FACTOR ** attempt) + random.uniform(0, 1)
                            print(f"Rate limited (429) for {model}. Retrying in {wait_time:.2f}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(f"Max retries reached for {model} (429).")
                            return None
                            
                    response.raise_for_status()

                    data = response.json()
                    message = data['choices'][0]['message']

                    return {
                        'content': message.get('content'),
                        'reasoning_details': message.get('reasoning_details')
                    }

            except httpx.HTTPStatusError as e:
                # Other HTTP errors
                print(f"HTTP error querying {model}: {e}")
                return None
            except Exception as e:
                print(f"Error querying model {model}: {e}")
                return None
                
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


async def query_model_stream(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
):
    """
    Query a model and stream the response tokens.
    
    Args:
        model: OpenRouter model identifier
        messages: List of message dicts
        timeout: Request timeout in seconds
        
    Yields:
        String chunks of the response content
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": True # Enable streaming
    }

    # Note: Scanning streaming responses for errors is tricky, 
    # but initial connection is covered here.
    semaphore = get_semaphore()

    async with semaphore:
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "POST", 
                        OPENROUTER_API_URL, 
                        headers=headers, 
                        json=payload
                    ) as response:
                        
                        if response.status_code == 429:
                             if attempt < MAX_RETRIES:
                                wait_time = (BACKOFF_FACTOR ** attempt) + random.uniform(0, 1)
                                print(f"Rate limited (429) for {model} [stream]. Retrying in {wait_time:.2f}s...")
                                await asyncio.sleep(wait_time)
                                continue
                             else:
                                yield f"[ERROR: Rate limit exceeded for {model}]"
                                return

                        response.raise_for_status()
                        
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str.strip() == "[DONE]":
                                    break
                                
                                try:
                                    data = json.loads(data_str)
                                    delta = data['choices'][0]['delta']
                                    content = delta.get('content')
                                    if content:
                                        yield content
                                except json.JSONDecodeError:
                                    continue
                        
                        # If successful stream, break retry loop
                        return
                                    
            except Exception as e:
                print(f"Error streaming model {model}: {e}")
                if attempt == MAX_RETRIES:
                    yield f"[ERROR: {str(e)}]"
                
            # Wait before retry if exception occurred
            if attempt < MAX_RETRIES:
                 await asyncio.sleep(1)

