"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# Rube MCP Server configuration
RUBE_MCP_URL = os.getenv("RUBE_MCP_URL", "https://rube.app/mcp")
RUBE_API_KEY = os.getenv("RUBE_API_KEY")

# Linear configuration
LINEAR_TEAM_ID = os.getenv("LINEAR_TEAM_ID")

# Composio configuration
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
COMPOSIO_MCP_SERVER_ID = os.getenv("COMPOSIO_MCP_SERVER_ID")

# Enable/disable tool-augmented deliberation
ENABLE_TOOLS = os.getenv("ENABLE_TOOLS", "false").lower() == "true"
