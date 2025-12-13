"""Composio MCP Gateway integration for LLM Council."""

import os
from typing import List, Dict, Any, Optional
from composio import Composio, Action


class ComposioClient:
    """
    Client for interacting with Composio MCP Gateway.
    
    This client manages:
    - MCP server configuration
    - User authentication and MCP URL generation
    - Tool discovery and execution
    - Tool result caching
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Composio client.
        
        Args:
            api_key: Composio API key (defaults to COMPOSIO_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("COMPOSIO_API_KEY")
        if not self.api_key:
            raise ValueError("COMPOSIO_API_KEY must be set in environment or passed to constructor")
        
        self.client = Composio(api_key=self.api_key)
        self.mcp_server_id = os.getenv("COMPOSIO_MCP_SERVER_ID")
        self._tool_cache = {}
    
    def get_or_create_mcp_server(
        self,
        name: str = "llm-council-gateway",
        toolkits: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Get existing MCP server or create a new one.
        
        Args:
            name: Name for the MCP server
            toolkits: List of toolkit configurations
                     Example: [{"toolkit": "github", "auth_config": "ac_xyz"}]
        
        Returns:
            MCP server configuration dict
        """
        # If server ID is configured, return it
        if self.mcp_server_id:
            return {"id": self.mcp_server_id}
        
        # Default toolkits if none provided
        if toolkits is None:
            toolkits = []
        
        # Create new MCP server
        try:
            server = self.client.mcp.create(
                name=name,
                toolkits=toolkits
            )
            return server
        except Exception as e:
            print(f"Warning: Could not create MCP server: {e}")
            print("Tools will not be available. Configure COMPOSIO_MCP_SERVER_ID in .env")
            return None
    
    def generate_user_mcp_url(self, user_id: str) -> Optional[str]:
        """
        Generate a user-specific MCP URL.
        
        Args:
            user_id: Unique identifier for the user
        
        Returns:
            MCP server URL for the user, or None if not configured
        """
        if not self.mcp_server_id:
            return None
        
        try:
            instance = self.client.mcp.generate(
                user_id=user_id,
                mcp_config_id=self.mcp_server_id
            )
            return instance.get('url')
        except Exception as e:
            print(f"Warning: Could not generate MCP URL for user {user_id}: {e}")
            return None
    
    def list_available_tools(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all tools available through Composio.
        
        Args:
            user_id: Optional user ID to get user-specific tools
        
        Returns:
            List of tool definitions with name, description, parameters
        """
        # Check cache first
        cache_key = f"tools_{user_id or 'default'}"
        if cache_key in self._tool_cache:
            return self._tool_cache[cache_key]
        
        try:
            # Get tools from Composio
            if user_id:
                tools = self.client.tools.list(user_id=user_id)
            else:
                tools = self.client.tools.list()
            
            # Format tools for council consumption
            formatted_tools = []
            for tool in tools:
                formatted_tools.append({
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                    "toolkit": tool.get("toolkit", "")
                })
            
            # Cache the results
            self._tool_cache[cache_key] = formatted_tools
            return formatted_tools
        
        except Exception as e:
            print(f"Warning: Could not list tools: {e}")
            return []
    
    def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool through Composio.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            user_id: Optional user ID for user-specific execution
        
        Returns:
            Tool execution result
        """
        try:
            # Execute the tool
            if user_id:
                result = self.client.execute_action(
                    action=tool_name,
                    params=parameters,
                    entity_id=user_id
                )
            else:
                result = self.client.execute_action(
                    action=tool_name,
                    params=parameters
                )
            
            return {
                "success": True,
                "result": result,
                "tool": tool_name
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name
            }
    
    def format_tools_for_prompt(
        self,
        tools: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Format tools as a string for inclusion in LLM prompts.
        
        Args:
            tools: Optional list of tools (will fetch if not provided)
            user_id: Optional user ID for user-specific tools
        
        Returns:
            Formatted string describing available tools
        """
        if tools is None:
            tools = self.list_available_tools(user_id)
        
        if not tools:
            return "No tools available."
        
        tool_descriptions = []
        for tool in tools:
            tool_descriptions.append(
                f"- **{tool['name']}** ({tool.get('toolkit', 'unknown')}): {tool['description']}"
            )
        
        return "\n".join(tool_descriptions)
    
    def is_configured(self) -> bool:
        """
        Check if Composio is properly configured.
        
        Returns:
            True if API key and server ID are set
        """
        return bool(self.api_key and self.mcp_server_id)


# Global instance
_composio_client = None


def get_composio_client() -> Optional[ComposioClient]:
    """
    Get or create the global Composio client instance.
    
    Returns:
        ComposioClient instance, or None if not configured
    """
    global _composio_client
    
    if _composio_client is None:
        try:
            _composio_client = ComposioClient()
        except ValueError:
            # Composio not configured, return None
            return None
    
    return _composio_client
