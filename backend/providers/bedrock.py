"""AWS Bedrock provider using the Converse API."""

import asyncio
from typing import List, Dict, Any, Optional
from ..config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION


def _get_client():
    """Create a boto3 Bedrock runtime client with explicit credentials."""
    import boto3
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def _convert_messages(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Convert standard message format to Bedrock Converse format."""
    return [
        {"role": msg["role"], "content": [{"text": msg["content"]}]}
        for msg in messages
    ]


def _call_bedrock(model: str, messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """Synchronous Bedrock call (run in thread)."""
    client = _get_client()
    bedrock_messages = _convert_messages(messages)

    response = client.converse(
        modelId=model,
        messages=bedrock_messages,
    )

    output_text = response["output"]["message"]["content"][0]["text"]
    return {
        "content": output_text,
        "reasoning_details": None,
    }


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a model via AWS Bedrock Converse API.

    Args:
        model: Bedrock model ID (e.g., "anthropic.claude-sonnet-4-5-20250514-v1:0")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_call_bedrock, model, messages),
            timeout=timeout,
        )
    except Exception as e:
        print(f"Error querying Bedrock model {model}: {e}")
        return None
