"""Ollama provider implementation."""

from __future__ import annotations

import logging
import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

from ..config import (
    OLLAMA_API_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_NUM_PREDICT,
    OLLAMA_THINK,
    OLLAMA_TIMEOUT,
)
from .base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama-backed provider for local multi-model councils."""

    @property
    def name(self) -> str:
        return "ollama"

    async def query_model(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": OLLAMA_THINK,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {"num_predict": OLLAMA_NUM_PREDICT},
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    OLLAMA_API_URL, json=payload, timeout=timeout or OLLAMA_TIMEOUT
                )
                response.raise_for_status()

            data = response.json()
            message = data.get("message", {})
            content = message.get("content")
            if not isinstance(content, str):
                raise ValueError("Ollama response did not contain message.content")
            return {
                "content": content,
                "reasoning_details": None,
                "usage": {
                    "prompt_tokens": data.get("prompt_eval_count"),
                    "completion_tokens": data.get("eval_count"),
                },
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except (httpx.TimeoutException, asyncio.TimeoutError):
            logger.warning("Ollama request timed out model=%s", model)
        except (httpx.ConnectError, httpx.HTTPStatusError) as exc:
            logger.warning("Ollama unavailable model=%s error=%s", model, exc)
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("Malformed Ollama response model=%s error=%s", model, exc)
        return None
