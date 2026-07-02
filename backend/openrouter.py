"""OpenRouter API client for making LLM requests."""

import asyncio
import httpx
from typing import List, Dict, Any, Optional
from .config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_ENDPOINT,
    BEDROCK_REGION,
    CHAIRMAN_MODEL,
    CHAIRMAN_REASONING_EFFORT,
    FIREWORKS_API_KEY,
    FIREWORKS_BASE_URL,
    LLM_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_API_URL,
)

PROVIDER_PREFIXES = ("openrouter:", "azure:", "fireworks:", "bedrock:")


def _provider_and_model(model: str) -> tuple[str, str]:
    """Return the provider and provider-native model name."""
    for prefix in PROVIDER_PREFIXES:
        if model.startswith(prefix):
            return prefix[:-1], model[len(prefix):]
    return LLM_PROVIDER, model


def _normalized_reasoning_effort(value: Optional[str]) -> Optional[str]:
    """Normalize friendly reasoning labels to API values."""
    if not value:
        return None
    effort = value.strip().lower().replace("_", " ").replace("-", " ")
    return {
        "extra high": "xhigh",
        "extra": "xhigh",
    }.get(effort, effort)


def _chat_payload_options(model: str) -> dict[str, Any]:
    """Return optional Chat Completions payload fields for a model call."""
    if model != CHAIRMAN_MODEL:
        return {}

    reasoning_effort = _normalized_reasoning_effort(CHAIRMAN_REASONING_EFFORT)
    if not reasoning_effort:
        return {}

    return {"reasoning_effort": reasoning_effort}


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
    provider, provider_model = _provider_and_model(model)

    if provider == "azure":
        return await query_azure_deployment(
            provider_model,
            messages,
            timeout,
            extra_payload=_chat_payload_options(model),
        )
    if provider == "fireworks":
        return await query_fireworks_model(provider_model, messages, timeout)
    if provider == "bedrock":
        return await query_bedrock_model(provider_model, messages, timeout)

    return await query_openrouter_model(provider_model, messages, timeout)


async def query_openrouter_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """Query a single model via OpenRouter API."""
    if not OPENROUTER_API_KEY:
        print("Error querying OpenRouter: OPENROUTER_API_KEY is not configured")
        return None

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

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_azure_deployment(
    deployment: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    extra_payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Query a single Azure OpenAI chat deployment."""
    if not AZURE_OPENAI_API_KEY:
        print("Error querying Azure OpenAI: AZURE_OPENAI_API_KEY is not configured")
        return None
    if not AZURE_OPENAI_ENDPOINT:
        print("Error querying Azure OpenAI: AZURE_OPENAI_ENDPOINT is not configured")
        return None

    url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{deployment}/chat/completions"
    headers = {
        "api-key": AZURE_OPENAI_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "messages": messages,
    }
    if extra_payload:
        payload.update(extra_payload)
    params = {
        "api-version": AZURE_OPENAI_API_VERSION,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                headers=headers,
                params=params,
                json=payload,
            )
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]

            return {
                "content": message.get("content"),
                "reasoning_details": message.get("reasoning_details"),
            }

    except Exception as e:
        print(f"Error querying Azure deployment {deployment}: {e}")
        return None


async def query_fireworks_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """Query a single Fireworks OpenAI-compatible chat model."""
    if not FIREWORKS_API_KEY:
        print("Error querying Fireworks: FIREWORKS_API_KEY is not configured")
        return None

    headers = {
        "Authorization": f"Bearer {FIREWORKS_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{FIREWORKS_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]

            return {
                "content": message.get("content"),
                "reasoning_details": message.get("reasoning_details"),
            }

    except Exception as e:
        print(f"Error querying Fireworks model {model}: {e}")
        return None


def _bedrock_text_blocks(content: Any) -> list[dict[str, str]]:
    """Convert app message content into Bedrock Converse text blocks."""
    if isinstance(content, str):
        return [{"text": content}]
    if isinstance(content, list):
        blocks = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                blocks.append({"text": item["text"]})
            elif isinstance(item, str):
                blocks.append({"text": item})
        if blocks:
            return blocks
    return [{"text": str(content)}]


def _bedrock_converse_payload(messages: List[Dict[str, str]]) -> dict[str, Any]:
    """Build a Bedrock Converse payload from OpenAI-style chat messages."""
    bedrock_messages = []
    system_blocks = []

    for message in messages:
        role = message.get("role", "user")
        blocks = _bedrock_text_blocks(message.get("content", ""))

        if role == "system":
            system_blocks.extend(blocks)
            continue

        bedrock_messages.append({
            "role": "assistant" if role == "assistant" else "user",
            "content": blocks,
        })

    payload: dict[str, Any] = {"messages": bedrock_messages}
    if system_blocks:
        payload["system"] = system_blocks
    return payload


def _query_bedrock_model_sync(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float,
) -> Optional[Dict[str, Any]]:
    """Query a single model via Amazon Bedrock Converse."""
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "bedrock-runtime",
            region_name=BEDROCK_REGION,
            config=Config(
                connect_timeout=10,
                read_timeout=int(timeout),
                retries={"max_attempts": 2},
            ),
        )
        response = client.converse(
            modelId=model,
            **_bedrock_converse_payload(messages),
        )

        content_blocks = response["output"]["message"].get("content", [])
        content = "\n".join(
            block["text"]
            for block in content_blocks
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )

        return {
            "content": content,
            "reasoning_details": None,
        }

    except Exception as e:
        print(f"Error querying Bedrock model {model}: {e}")
        return None


async def query_bedrock_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """Query a single model via Amazon Bedrock Converse."""
    return await asyncio.to_thread(_query_bedrock_model_sync, model, messages, timeout)


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
