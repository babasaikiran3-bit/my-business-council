"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# API Provider configuration
# Supports both OpenRouter and Unbound backends
API_PROVIDER = os.getenv("API_PROVIDER", "openrouter")  # "openrouter" or "unbound"

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Unbound configuration
UNBOUND_API_KEY = os.getenv("UNBOUND_API_KEY")
UNBOUND_API_URL = "https://api.getunbound.ai/v1/chat/completions"

# Active API configuration (based on provider)
def get_api_config():
    """Returns the active API key and URL based on configured provider."""
    if API_PROVIDER == "unbound":
        return UNBOUND_API_KEY, UNBOUND_API_URL
    return OPENROUTER_API_KEY, OPENROUTER_API_URL

# Council members - model identifiers
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
