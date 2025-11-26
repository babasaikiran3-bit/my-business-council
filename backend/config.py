"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Router type: 'openrouter' or 'ollama'
ROUTER_TYPE = os.getenv("ROUTER_TYPE", "openrouter").lower()

# OpenRouter settings
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = os.getenv(
    "OPENROUTER_API_URL",
    "https://openrouter.ai/api/v1/chat/completions"
)

# Ollama settings
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost:11434")

# Council members - list of model identifiers
# Parse from comma-separated string or use default
COUNCIL_MODELS_STR = os.getenv("COUNCIL_MODELS")
if COUNCIL_MODELS_STR:
    COUNCIL_MODELS = [model.strip() for model in COUNCIL_MODELS_STR.split(",")]
else:
    # Default models based on router type
    if ROUTER_TYPE == "ollama":
        COUNCIL_MODELS = [
            "deepseek-r1:latest",
            "llama3.1:latest",
            "qwen3:latest",
            "gemma3:latest",
        ]
    else:
        COUNCIL_MODELS = [
            "openai/gpt-5.1",
            "google/gemini-3-pro-preview",
            "anthropic/claude-sonnet-4.5",
            "x-ai/grok-4",
        ]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = os.getenv("CHAIRMAN_MODEL")
if not CHAIRMAN_MODEL:
    # Default chairman model based on router type
    if ROUTER_TYPE == "ollama":
        CHAIRMAN_MODEL = "gemma3:latest"
    else:
        CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# Data directory for conversation storage
DATA_DIR = os.getenv("DATA_DIR", "data/conversations")

# Timeout settings (in seconds)
DEFAULT_TIMEOUT = float(os.getenv("DEFAULT_TIMEOUT", "120.0"))
TITLE_GENERATION_TIMEOUT = float(os.getenv("TITLE_GENERATION_TIMEOUT", "180.0"))

# Validate configuration
if ROUTER_TYPE not in ["openrouter", "ollama"]:
    raise ValueError(
        f"Invalid ROUTER_TYPE: {ROUTER_TYPE}. Must be 'openrouter' or 'ollama'"
    )

if ROUTER_TYPE == "openrouter" and not OPENROUTER_API_KEY:
    raise ValueError(
        "OPENROUTER_API_KEY is required when ROUTER_TYPE=openrouter"
    )