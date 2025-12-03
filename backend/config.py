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
    "x-ai/grok-4"
]

# Custom models configuration
# Format: { "model_id": { "api_url": "...", "api_key": "..." } }
CUSTOM_MODELS = {
    # Example for a local Ollama model:
    # "ollama/llama3": {
    #     "api_url": "http://localhost:11434/v1/chat/completions",
    #     "api_key": "ollama"  # key is often ignored by local servers but required by some clients
    # }
}

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
