"""OpenAI Direct API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional
from ..config import OPENAI_API_KEY

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenAI's API directly.

    Args:
        model: Model identifier (e.g., "gpt-5.1" or "openai/gpt-5.1")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    # Strip provider prefix if present (e.g., "openai/gpt-5.1" -> "gpt-5.1")
    model_name = model.split("/")[-1]

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_name,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENAI_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details') or message.get('reasoning_content')
            }

    except Exception as e:
        print(f"Error querying OpenAI model {model_name}: {e}")
        return None
