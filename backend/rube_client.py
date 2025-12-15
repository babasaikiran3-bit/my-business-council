"""Rube MCP Server integration for LLM Council DevOps Platform."""

import os
import httpx
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


class RubeMCPClient:
    """
    Client for interacting with Rube MCP Server.
    
    Rube is a Model Context Protocol (MCP) server that connects AI tools
    to 500+ apps like Gmail, Slack, GitHub, Linear, Figma, Sentry, etc.
    
    This client manages:
    - MCP server connection
    - Tool discovery
    - Tool execution via MCP protocol
    - Authentication and session management
    """
    
    def __init__(self, mcp_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize Rube MCP client.
        
        Args:
            mcp_url: Rube MCP server URL (defaults to RUBE_MCP_URL env var)
            api_key: API key for authentication (defaults to RUBE_API_KEY env var)
        """
        self.mcp_url = mcp_url or os.getenv("RUBE_MCP_URL", "https://rube.app/mcp")
        self.api_key = api_key or os.getenv("RUBE_API_KEY")
        
        if not self.api_key:
            raise ValueError("RUBE_API_KEY must be set in environment or passed to constructor")
        
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        self._tool_cache = {}
    
    async def list_available_tools(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all tools available through Rube MCP Server.
        
        Args:
            user_id: Optional user ID for user-specific tools
        
        Returns:
            List of tool definitions with name, description, parameters
        """
        # Check cache first
        cache_key = f"tools_{user_id or 'default'}"
        if cache_key in self._tool_cache:
            return self._tool_cache[cache_key]
        
        try:
            # Call MCP server to list tools
            response = await self.client.post(
                f"{self.mcp_url}/tools/list",
                json={"user_id": user_id} if user_id else {}
            )
            response.raise_for_status()
            
            tools = response.json().get("tools", [])
            
            # Cache the results
            self._tool_cache[cache_key] = tools
            return tools
        
        except Exception as e:
            print(f"Warning: Could not list tools from Rube MCP: {e}")
            return []
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool through Rube MCP Server.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            user_id: Optional user ID for user-specific execution
        
        Returns:
            Tool execution result
        """
        try:
            # Call MCP server to execute tool
            response = await self.client.post(
                f"{self.mcp_url}/tools/execute",
                json={
                    "tool": tool_name,
                    "parameters": parameters,
                    "user_id": user_id
                }
            )
            response.raise_for_status()
            
            result = response.json()
            
            return {
                "success": True,
                "result": result.get("data"),
                "tool": tool_name
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name
            }
    
    async def create_linear_issue(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        team_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new issue in Linear.
        
        Args:
            title: Issue title
            description: Issue description
            priority: Issue priority (low, medium, high, urgent)
            team_id: Linear team ID
            user_id: Optional user ID for authentication
        
        Returns:
            Created issue data
        """
        return await self.execute_tool(
            tool_name="LINEAR_CREATE_ISSUE",
            parameters={
                "title": title,
                "description": description,
                "priority": priority,
                "teamId": team_id
            },
            user_id=user_id
        )
    
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an email via Gmail.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            user_id: Optional user ID for authentication
        
        Returns:
            Email send result
        """
        return await self.execute_tool(
            tool_name="GMAIL_SEND_EMAIL",
            parameters={
                "to": to,
                "subject": subject,
                "body": body
            },
            user_id=user_id
        )
    
    async def send_slack_message(
        self,
        channel: str,
        message: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message to Slack.
        
        Args:
            channel: Slack channel ID or name
            message: Message text
            user_id: Optional user ID for authentication
        
        Returns:
            Slack message send result
        """
        return await self.execute_tool(
            tool_name="SLACK_SEND_MESSAGE",
            parameters={
                "channel": channel,
                "text": message
            },
            user_id=user_id
        )
    
    def format_tools_for_prompt(
        self,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Format tools as a string for inclusion in LLM prompts.
        
        Args:
            tools: Optional list of tools (will use cached if not provided)
        
        Returns:
            Formatted string describing available tools
        """
        if tools is None:
            # Use cached tools if available
            tools = self._tool_cache.get("tools_default", [])
        
        if not tools:
            return "No tools available."
        
        tool_descriptions = []
        for tool in tools:
            tool_descriptions.append(
                f"- **{tool['name']}**: {tool.get('description', 'No description')}"
            )
        
        return "\n".join(tool_descriptions)
    
    def is_configured(self) -> bool:
        """
        Check if Rube MCP is properly configured.
        
        Returns:
            True if API key and URL are set
        """
        return bool(self.api_key and self.mcp_url)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global instance
_rube_client = None


async def get_rube_client() -> Optional[RubeMCPClient]:
    """
    Get or create the global Rube MCP client instance.
    
    Returns:
        RubeMCPClient instance, or None if not configured
    """
    global _rube_client
    
    if _rube_client is None:
        try:
            _rube_client = RubeMCPClient()
        except ValueError:
            # Rube not configured, return None
            return None
    
    return _rube_client
