"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Nebius API key
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")

# Nebius API endpoint
NEBIUS_API_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"

# Local API key
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY")

# Local API endpoint
LOCAL_API_URL = "http://host.docker.internal:11434/v1/chat/completions"




# Council members - list of OpenRouter model identifiers
# COUNCIL_MODELS = [
#     "openai/gpt-5.1",
#     "google/gemini-3-pro-preview",
#     "anthropic/claude-sonnet-4.5",
#     "x-ai/grok-4",
# ]

COUNCIL_MODELS = [
    {
        "id": "nebius-Qwen3-Coder-480B-A35B-Instruct",
        "provider": "nebius",
        "model":"Qwen/Qwen3-Coder-480B-A35B-Instruct"
    },
    {
        "id": "local-deepseek-coder:6.7b",
        "provider": "local",
        "model": "deepseek-coder:6.7b",
    }
]

# Chairman model - synthesizes final response
# CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

CHAIRMAN_MODEL = {
        "id": "gpt-oss:20b",
        "provider": "nebius",
        "model":"openai/gpt-oss-120b"
    }

# Data directory for conversation storage
DATA_DIR = "data/conversations"
