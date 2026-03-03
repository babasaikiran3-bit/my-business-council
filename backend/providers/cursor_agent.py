"""Cursor Agent provider using the cursor-agent CLI."""

import asyncio
import json
import os
from typing import List, Dict, Any, Optional
from ..config import CURSOR_API_KEY


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 180.0
) -> Optional[Dict[str, Any]]:
    """
    Query a model via cursor-agent CLI.

    Args:
        model: Model identifier for cursor-agent (e.g., "sonnet-4.6")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    # Build prompt from messages: concatenate all messages with role prefixes
    prompt_parts = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            prompt_parts.append(content)
        else:
            prompt_parts.append(f"[{role}]: {content}")
    prompt = "\n\n".join(prompt_parts)

    # Set up environment with API key if configured
    env = os.environ.copy()
    if CURSOR_API_KEY:
        env["CURSOR_API_KEY"] = CURSOR_API_KEY

    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            "cursor-agent", "-p",
            "--output-format", "json",
            "--model", model,
            "--mode", "ask",
            "--trust",
            prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )

        if process.returncode != 0:
            print(f"cursor-agent exited with code {process.returncode}: {stderr.decode()}")
            return None

        result = json.loads(stdout.decode())

        if result.get("is_error"):
            print(f"cursor-agent returned error: {result}")
            return None

        return {
            "content": result.get("result", ""),
            "reasoning_details": None,
        }

    except asyncio.TimeoutError:
        print(f"Timeout querying cursor-agent model {model} (>{timeout}s)")
        if process:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        return None
    except Exception as e:
        print(f"Error querying cursor-agent model {model}: {e}")
        return None
