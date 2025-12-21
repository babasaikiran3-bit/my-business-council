"""OpenRouter API client for making LLM requests."""

import json
import httpx
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


async def query_model(
    model: str,
    messages: List[Dict[str, Any]],
    timeout: float = 120.0,
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tool_iterations: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API with optional tool support.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
        tools: Optional list of tool definitions (OpenAI function calling format)
        max_tool_iterations: Maximum number of tool call iterations to prevent infinite loops

    Returns:
        Response dict with 'content', optional 'reasoning_details',
        and optional 'tool_calls_made', or None if failed
    """
    from .tools import execute_tool

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Work with a copy of messages to avoid mutating the original
    current_messages = [msg.copy() for msg in messages]
    tool_calls_made = []

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            for _ in range(max_tool_iterations):
                payload = {
                    "model": model,
                    "messages": current_messages,
                }

                # Add tools to payload if provided
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"

                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                data = response.json()
                choice = data['choices'][0]
                message = choice['message']
                finish_reason = choice.get('finish_reason')

                # Check if model wants to call tools
                if message.get('tool_calls') or finish_reason == 'tool_calls':
                    tool_calls = message.get('tool_calls', [])

                    if not tool_calls:
                        # No tool calls despite finish_reason, return content
                        break

                    # Add assistant message with tool calls to conversation
                    current_messages.append(message)

                    # Execute each tool call
                    for tool_call in tool_calls:
                        tool_name = tool_call['function']['name']
                        try:
                            tool_args = json.loads(tool_call['function']['arguments'])
                        except json.JSONDecodeError:
                            tool_args = {}

                        # Execute the tool
                        result = await execute_tool(tool_name, tool_args)

                        # Track tool usage
                        tool_calls_made.append({
                            'tool': tool_name,
                            'args': tool_args,
                            'result': result
                        })

                        # Add tool result to messages
                        current_messages.append({
                            'role': 'tool',
                            'tool_call_id': tool_call['id'],
                            'content': json.dumps(result)
                        })

                    # Continue loop to get model's response with tool results
                    continue
                else:
                    # Model returned regular content, we're done
                    result = {
                        'content': message.get('content'),
                        'reasoning_details': message.get('reasoning_details')
                    }

                    # Include tool calls made if any
                    if tool_calls_made:
                        result['tool_calls_made'] = tool_calls_made

                    return result

            # Max iterations reached, return whatever content we have
            return {
                'content': message.get('content', ''),
                'reasoning_details': message.get('reasoning_details'),
                'tool_calls_made': tool_calls_made if tool_calls_made else None
            }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        tools: Optional list of tool definitions to pass to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages, tools=tools) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
