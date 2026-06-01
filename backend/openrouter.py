"""OpenRouter API client for making LLM requests."""

import logging
import httpx
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL

logger = logging.getLogger("parenting_roundtable.openrouter")


def _hostname_in_allowlist(url: str, allowed_domains: List[str]) -> bool:
    """True if the URL's hostname equals or is a subdomain of an allowed domain."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    if not host:
        return False
    for domain in allowed_domains:
        d = domain.lower().lstrip(".")
        if host == d or host.endswith("." + d):
            return True
    return False


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    web_search: bool = False,
    search_domains: Optional[List[str]] = None,
    max_results: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
        web_search: If True, enable the Exa web search plugin
        search_domains: Domains to restrict web search to (include_domains)
        max_results: Maximum number of web search results to retrieve

    Returns:
        Response dict with 'content', optional 'reasoning_details', and
        'annotations' (web citations), or None if failed
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    if web_search:
        web_plugin: Dict[str, Any] = {
            "id": "web",
            "engine": "exa",
            "max_results": max_results,
            "search_prompt": "Authoritative medical and scientific sources relevant to this pediatric question:",
        }
        if search_domains:
            web_plugin["include_domains"] = search_domains
        payload["plugins"] = [web_plugin]

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
                'reasoning_details': message.get('reasoning_details'),
                'annotations': message.get('annotations'),
            }

    except Exception as e:
        logger.warning("query_model failed", extra={"model": model, "error": str(e)})
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    **kwargs: Any
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        **kwargs: Forwarded to each query_model call (e.g. web_search, timeout)

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages, **kwargs) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}


def extract_citations(
    annotations: Optional[List[Dict[str, Any]]],
    allowed_domains: Optional[List[str]] = None
) -> List[Dict[str, str]]:
    """
    Extract real web citations from OpenRouter message annotations.

    Args:
        annotations: The 'annotations' list from a message, or None
        allowed_domains: If provided, drop any citation whose hostname is not
            within this allowlist. Defense-in-depth: even if the search engine
            ignores include_domains, a non-trusted URL can never be surfaced to
            the user as an authoritative source.

    Returns:
        List of {"url", "title"} dicts, deduped by url, order-preserving.
        Title falls back to the url if absent.
    """
    citations: List[Dict[str, str]] = []
    seen_urls = set()

    if not annotations:
        return citations

    for item in annotations:
        if not isinstance(item, dict):
            continue
        url_citation = item.get("url_citation")
        if not isinstance(url_citation, dict):
            continue
        url = url_citation.get("url")
        if not url or url in seen_urls:
            continue
        if allowed_domains and not _hostname_in_allowlist(url, allowed_domains):
            continue
        seen_urls.add(url)
        title = url_citation.get("title") or url
        citations.append({"url": url, "title": title})

    return citations
