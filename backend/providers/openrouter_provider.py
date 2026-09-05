"""OpenRouter-compatible API provider implementation."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from ..config import OPENROUTER_API_KEY, OPENROUTER_API_URL
from .base import LLMProvider

logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    """Provider for OpenRouter and OpenRouter-compatible chat APIs."""

    @property
    def name(self) -> str:
        return "api"

    async def query_model(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is required for the API provider.")

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout or 120.0) as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"model": model, "messages": messages},
                )
                response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]
            return {
                "content": message.get("content"),
                "reasoning_details": message.get("reasoning_details"),
                "usage": data.get("usage"),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("API model request failed model=%s error=%s", model, exc)
            return None
