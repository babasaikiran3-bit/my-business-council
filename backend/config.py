"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers
# NOTE: For Discord bot, you can use fewer models to reduce costs
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    # "x-ai/grok-4",  # Uncomment to add more council members
]

# Chairman model - synthesizes final response
# Opus 4.1 recommended for high-quality synthesis
CHAIRMAN_MODEL = "anthropic/claude-opus-4.1"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
