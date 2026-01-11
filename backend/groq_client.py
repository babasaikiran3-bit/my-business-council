import httpx
import asyncio
from typing import List, Dict, Any, Optional
from .config import GROQ_API_KEY, GROQ_API_URL


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via Groq API.
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": 1.0,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                GROQ_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            return {
                'content': message.get('content', ''),
                'model': model,
                'usage': data.get('usage', {}),
                'finish_reason': data['choices'][0].get('finish_reason', 'stop')
            }

    except Exception as e:
        print(f"Error querying model {model}: {type(e).__name__}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    max_concurrent: int = 5
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def query_with_semaphore(model):
        async with semaphore:
            return await query_model(model, messages, temperature, max_tokens)

    tasks = [query_with_semaphore(model) for model in models]
    responses = await asyncio.gather(*tasks)
    
    return {model: response for model, response in zip(models, responses)}