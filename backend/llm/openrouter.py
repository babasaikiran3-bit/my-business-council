"""OpenRouter LLM provider implementation."""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional

import httpx

from ..config import OPENROUTER_API_KEY, OPENROUTER_API_URL
from .base import LLMProvider, LLMResponse, ProgressCallback

logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    """LLM provider implementation for OpenRouter API.
    
    OpenRouter provides a unified API for accessing multiple LLM providers
    (OpenAI, Anthropic, Google, etc.) through a single endpoint.
    """
    
    # Default timeout: 8 minutes to accommodate slow models like gpt-5.2-pro
    DEFAULT_TIMEOUT = 480.0
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        default_timeout: Optional[float] = None,
    ):
        """Initialize the OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key (uses config default if None).
            api_url: OpenRouter API URL (uses config default if None).
            default_timeout: Default timeout in seconds (uses class default if None).
        """
        self._api_key = api_key or OPENROUTER_API_KEY
        self._api_url = api_url or OPENROUTER_API_URL
        self._default_timeout = default_timeout or self.DEFAULT_TIMEOUT
    
    @property
    def name(self) -> str:
        return "openrouter"
    
    @property
    def default_timeout(self) -> float:
        return self._default_timeout
    
    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: Optional[float] = None,
    ) -> Optional[LLMResponse]:
        """Query a single model via OpenRouter API."""
        timeout = timeout or self._default_timeout
        
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": messages,
        }
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self._api_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                message = data['choices'][0]['message']
                
                content = message.get('content')
                if not content:
                    logger.warning(f"[OPENROUTER] Model {model} returned empty content.")
                
                return LLMResponse(
                    content=content,
                    reasoning_details=message.get('reasoning_details'),
                    raw_response=data,
                )
                
        except httpx.HTTPStatusError as e:
            self._log_http_error(model, e)
            return None
        except httpx.TimeoutException as e:
            logger.error(f"[OPENROUTER] Request timeout for model {model}: {e}")
            return None
        except Exception as e:
            logger.error(f"[OPENROUTER] Unexpected error querying model {model}: {e}")
            return None
    
    async def query_parallel(
        self,
        models: List[str],
        messages: List[Dict[str, str]],
        timeout: Optional[float] = None,
    ) -> Dict[str, Optional[LLMResponse]]:
        """Query multiple models in parallel."""
        tasks = [self.query(model, messages, timeout=timeout) for model in models]
        responses = await asyncio.gather(*tasks)
        return {model: response for model, response in zip(models, responses)}
    
    async def query_parallel_with_progress(
        self,
        models: List[str],
        messages: List[Dict[str, str]],
        on_model_complete: Optional[ProgressCallback] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Optional[LLMResponse]]:
        """Query multiple models in parallel with progress callbacks."""
        results: Dict[str, Optional[LLMResponse]] = {}
        
        async def query_with_callback(model: str):
            start_time = time.time()
            response = await self.query(model, messages, timeout=timeout)
            elapsed_ms = int((time.time() - start_time) * 1000)
            success = response is not None and response.success
            if on_model_complete:
                await on_model_complete(model, response, success, elapsed_ms)
            return model, response
        
        tasks = [query_with_callback(model) for model in models]
        
        for coro in asyncio.as_completed(tasks):
            model, response = await coro
            results[model] = response
        
        return results
    
    def _log_http_error(self, model: str, e: httpx.HTTPStatusError) -> None:
        """Log HTTP errors with appropriate detail level."""
        status_code = e.response.status_code
        error_messages = {
            429: "Rate limit exceeded",
            401: "Authentication failed",
            402: "Payment required (insufficient credits)",
            403: "Access forbidden",
            404: "Model not found",
        }
        
        if status_code == 400:
            try:
                error_body = e.response.json()
                msg = error_body.get('error', {}).get('message', str(e))
                logger.error(f"[OPENROUTER] Bad request for model {model}: {msg}")
            except Exception:
                logger.error(f"[OPENROUTER] Bad request for model {model}: {e}")
        elif status_code in error_messages:
            logger.error(f"[OPENROUTER] {error_messages[status_code]} for model {model}: {e}")
        elif status_code >= 500:
            logger.error(f"[OPENROUTER] Server error ({status_code}) for model {model}: {e}")
        else:
            logger.error(f"[OPENROUTER] HTTP {status_code} error for model {model}: {e}")

