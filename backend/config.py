"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# API keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CURSOR_API_KEY = os.getenv("CURSOR_API_KEY")

# AWS credentials
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Council members - list of model config dicts
COUNCIL_MODELS = [
    {"provider": "cursor_agent", "model": "gpt-5.2"},
    {"provider": "cursor_agent", "model": "gemini-3.1-pro"},
    {"provider": "cursor_agent", "model": "sonnet-4.6"},
    {"provider": "cursor_agent", "model": "grok"},
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = {"provider": "cursor_agent", "model": "gemini-3.1-pro"}

# Title generation model (fast and cheap)
TITLE_MODEL = {"provider": "cursor_agent", "model": "gemini-3-flash"}

# Ports
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8001"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "5173"))

# Data directory for conversation storage
DATA_DIR = "data/conversations"


def get_model_name(model_config) -> str:
    """Get display name for a model config. Uses 'name' override if present, else 'model'."""
    if isinstance(model_config, str):
        return model_config
    return model_config.get("name", model_config["model"])
