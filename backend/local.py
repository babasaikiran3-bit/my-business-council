"""Ollama (local) provider with adaptive resource safeguards."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import (
    OLLAMA_BASE_URL,
    COUNCIL_MEM_RESERVE_GB,
    COUNCIL_MAX_PARALLEL_LOCAL,
    COUNCIL_ADAPTIVE_RESOURCE_GUARD,
    COUNCIL_LOCAL_TIMEOUT_SEC,
)

GiB = 1024 ** 3


async def _get_total_ram_bytes() -> int:
    """Return total system RAM in bytes (best-effort)."""
    try:
        import psutil  # type: ignore
        return int(psutil.virtual_memory().total)
    except Exception:
        # Fallback to a conservative default if psutil is not available at runtime
        return 8 * GiB


async def _fetch_installed_model_sizes() -> Dict[str, int]:
    """
    Ask the Ollama daemon for installed models and sizes.
    Returns map of model name -> size in bytes.
    """
    url = f"{OLLAMA_BASE_URL}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            sizes: Dict[str, int] = {}
            for m in data.get("models", []):
                name = m.get("name")
                size = m.get("size")
                if isinstance(name, str) and isinstance(size, int):
                    sizes[name.split(":")[0]] = size  # normalize "name:tag" -> "name"
            return sizes
    except Exception:
        return {}


# Conservative default size hints if Ollama does not return sizes
DEFAULT_SIZE_HINTS_GB: Dict[str, float] = {
    "nemotron": 4.9,
    "nemotron9b": 6.5,
    "nemotron12b": 7.5,
}


def _estimate_weight_bytes(model: str, size_bytes: Optional[int]) -> int:
    """
    Estimate memory weight for scheduling. We multiply file size by 1.3
    as a rough upper bound for runtime memory, with a minimum floor of 2 GiB.
    """
    if size_bytes is None or size_bytes <= 0:
        size_gb = DEFAULT_SIZE_HINTS_GB.get(model.split(":")[0], 3.0)
        size_bytes = int(size_gb * GiB)
    weight = int(size_bytes * 1.3)
    return max(weight, 2 * GiB)


def _compute_budget_bytes(total_ram_bytes: int) -> int:
    """
    Compute a memory budget for concurrent model runs, keeping a reserve.
    We take max(60% of total, total - reserve).
    """
    reserve_bytes = int(COUNCIL_MEM_RESERVE_GB * GiB)
    sixty_percent = int(total_ram_bytes * 0.60)
    return max(sixty_percent, total_ram_bytes - reserve_bytes)


class WeightedResourcePool:
    """Async weighted resource pool for memory-guarded concurrency."""

    def __init__(self, total_budget_bytes: int):
        self._total = total_budget_bytes
        self._used = 0
        self._cond = asyncio.Condition()

    @asynccontextmanager
    async def hold(self, weight_bytes: int):
        async with self._cond:
            while self._used + weight_bytes > self._total:
                await self._cond.wait()
            self._used += weight_bytes
        try:
            yield
        finally:
            async with self._cond:
                self._used = max(0, self._used - weight_bytes)
                self._cond.notify_all()


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = COUNCIL_LOCAL_TIMEOUT_SEC
) -> Optional[Dict[str, Any]]:
    """
    Query a single local model via Ollama chat API.
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            # Non-stream response typically includes 'message': {'content': ...}
            content = None
            if isinstance(data, dict):
                message = data.get("message") or {}
                content = message.get("content") or data.get("response")
            return {"content": content or ""}
    except Exception as e:
        print(f"[local] Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple local models in parallel with adaptive safeguards:
      - WeightedResourcePool to keep memory usage under a computed budget
      - Optional hard cap on max concurrent local runs
    """
    # Gather model size hints
    installed_sizes = await _fetch_installed_model_sizes()
    weights = {m: _estimate_weight_bytes(m, installed_sizes.get(m)) for m in models}

    # Compute memory budget
    total_ram = await _get_total_ram_bytes()
    budget = _compute_budget_bytes(total_ram)
    pool = WeightedResourcePool(budget) if COUNCIL_ADAPTIVE_RESOURCE_GUARD else None

    # Optional hard cap
    semaphore = asyncio.Semaphore(COUNCIL_MAX_PARALLEL_LOCAL) if COUNCIL_MAX_PARALLEL_LOCAL else None

    async def run_one(model: str) -> Optional[Dict[str, Any]]:
        async def call():
            return await query_model(model, messages)

        if pool is not None and semaphore is not None:
            async with semaphore:
                async with pool.hold(weights[model]):
                    return await call()
        elif pool is not None:
            async with pool.hold(weights[model]):
                return await call()
        elif semaphore is not None:
            async with semaphore:
                return await call()
        else:
            return await call()

    tasks = [run_one(m) for m in models]
    results = await asyncio.gather(*tasks)
    return {m: r for m, r in zip(models, results)}


