"""Multi-provider LLM client.

Model identifiers are "<provider>/<model>", e.g. "anthropic/claude-opus-5".
Every provider except Anthropic exposes an OpenAI-compatible
/chat/completions endpoint, so those three share one request/response shape.
Anthropic uses /v1/messages: different auth header, required max_tokens,
and a content-block response instead of choices[].
"""

import asyncio
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import ANTHROPIC_MAX_TOKENS, ANTHROPIC_VERSION, PROVIDERS


class ProviderError(RuntimeError):
    """Raised when a model identifier or its API key is unusable."""


def split_model_id(model_id: str) -> Tuple[str, str]:
    """Split "<provider>/<model>" into its parts, validating the provider."""
    provider, sep, model = model_id.partition("/")
    if not sep or not model:
        raise ProviderError(
            f"Model '{model_id}' must be '<provider>/<model>', e.g. 'openai/gpt-5.1'"
        )
    if provider not in PROVIDERS:
        raise ProviderError(
            f"Unknown provider '{provider}' in '{model_id}'. "
            f"Known providers: {', '.join(sorted(PROVIDERS))}"
        )
    return provider, model


def build_request(
    model_id: str,
    messages: List[Dict[str, str]],
) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """Build (url, headers, payload) for one provider's chat endpoint."""
    provider, model = split_model_id(model_id)
    spec = PROVIDERS[provider]

    api_key = os.getenv(spec["key_env"])
    if not api_key:
        raise ProviderError(
            f"{spec['key_env']} is not set, required for '{model_id}'. "
            f"Add it to the .env file in the project root."
        )

    if provider == "anthropic":
        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "messages": messages,
        }
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "messages": messages}

    return spec["url"], headers, payload


def parse_response(provider: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a provider response to {'content', 'reasoning_details'}."""
    if provider == "anthropic":
        # content is a list of blocks; concatenate the text ones and skip
        # thinking/tool blocks.
        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
        return {"content": text, "reasoning_details": None}

    message = data["choices"][0]["message"]
    return {
        "content": message.get("content"),
        "reasoning_details": message.get("reasoning_details"),
    }


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model on its native provider API.

    Args:
        model: "<provider>/<model>" identifier (e.g. "anthropic/claude-opus-5")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    try:
        provider, _ = split_model_id(model)
        url, headers, payload = build_request(model, messages)
    except ProviderError as e:
        print(f"Config error for {model}: {e}")
        return None

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return parse_response(provider, response.json())

    except httpx.HTTPStatusError as e:
        # The body carries the real reason: bad key, unknown model, no quota.
        body = e.response.text[:300]
        print(f"Error querying {model}: HTTP {e.response.status_code} - {body}")
        return None
    except Exception as e:
        print(f"Error querying {model}: {type(e).__name__}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of "<provider>/<model>" identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)
    return {model: response for model, response in zip(models, responses)}
