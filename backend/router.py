import httpx
from typing import List, Dict, Any, Optional
import asyncio
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL, NEBIUS_API_KEY, NEBIUS_API_URL, LOCAL_API_KEY, LOCAL_API_URL


async def query_model(
    model: Dict[str, Any],
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:

    if (model["provider"] == "local"):
        headers = {
            "Authorization": f"Bearer {LOCAL_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model["model"],
            "messages": messages,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    LOCAL_API_URL,
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

        except Exception as e:
            model_name = model["model"]
            print(f"Error querying model {model_name}: {e}")
            return None
        
    if (model["provider"] == "nebius"):
        headers = {
            "Authorization": f"Bearer {NEBIUS_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model["model"],
            "messages": messages,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    NEBIUS_API_URL,
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

        except Exception as e:
            model_name = model["model"]
            print(f"Error querying model {model_name}: {e}")
            return None


async def query_models_parallel(
    models: List[Dict[str, Any]],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    
    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model["model"]: response for model, response in zip(models, responses)}
