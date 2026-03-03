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
    {"provider": "openrouter", "model": "openai/gpt-5.1"},
    {"provider": "openrouter", "model": "google/gemini-3-pro-preview"},
    {"provider": "openrouter", "model": "anthropic/claude-sonnet-4.5"},
    {"provider": "openrouter", "model": "x-ai/grok-4"},
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = {"provider": "openrouter", "model": "google/gemini-3-pro-preview"}

# Title generation model (fast and cheap)
TITLE_MODEL = {"provider": "openrouter", "model": "google/gemini-2.5-flash"}

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
