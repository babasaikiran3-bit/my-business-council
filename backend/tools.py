"""Tool definitions and execution for LLM Council."""

from typing import Dict, Any, List
from .config import TAVILY_API_KEY, ENABLE_WEB_SEARCH

# Tavily web search tool definition (OpenAI function calling format)
TAVILY_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for current information. Use this when the question requires up-to-date information, recent news, current events, or facts that may have changed recently.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to execute"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-10)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
}


def get_available_tools() -> List[Dict[str, Any]]:
    """Get list of available tools based on configuration."""
    tools: List[Dict[str, Any]] = []
    if ENABLE_WEB_SEARCH and TAVILY_API_KEY:
        tools.append(TAVILY_SEARCH_TOOL)
    return tools


async def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool by name with given arguments.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments to pass to the tool

    Returns:
        Tool execution result as a dict
    """
    if tool_name == "web_search":
        return await execute_web_search(**tool_args)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


async def execute_web_search(
    query: str,
    max_results: int = 5
) -> Dict[str, Any]:
    """
    Execute a web search using Tavily API.

    Args:
        query: The search query
        max_results: Maximum number of results (1-10)

    Returns:
        Search results as a dict
    """
    if not TAVILY_API_KEY:
        return {"error": "Tavily API key not configured"}

    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=TAVILY_API_KEY)

        # Clamp max_results to valid range
        max_results = max(1, min(10, max_results))

        response = await client.search(
            query=query,
            max_results=max_results,
            include_answer=True
        )

        # Format results for the model
        results = []
        for result in response.get("results", []):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", "")
            })

        return {
            "query": query,
            "answer": response.get("answer"),
            "results": results
        }

    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}
