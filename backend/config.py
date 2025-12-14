"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Provider API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Council members - testing with cheap models
# Production models:
#   - "gpt-5.2" ($1.75/1M input)
#   - "gemini-3.0-pro"
#   - "claude-opus-4-5-20251101" ($5/1M input)
# Testing models (85-90% cheaper):
COUNCIL_MODELS = [
    "gpt-5-mini",                  # $0.25/1M input (86% cheaper)
    "gemini-2.5-flash-lite",       # ~90% cheaper
    "claude-haiku-4-5-20251001",   # $1/1M input (80% cheaper)
]

# Chairman model - also using cheap model for testing
# Production: "claude-sonnet-4-5-20250929"
# Testing:
CHAIRMAN_MODEL = "claude-haiku-4-5-20251001"

# Model to provider mapping
MODEL_PROVIDER_MAP = {
    # OpenAI models
    "gpt-5.2": "openai",
    "gpt-5.2-instant": "openai",
    "gpt-5-mini": "openai",

    # Google models
    "gemini-3.0-pro": "google",
    "gemini-3-pro-latest": "google",
    "gemini-2.5-flash-lite": "google",

    # Anthropic models
    "claude-opus-4-5-20251101": "anthropic",
    "claude-sonnet-4-5-20250929": "anthropic",
    "claude-haiku-4-5-20251001": "anthropic",
}

# Data directory for conversation storage
DATA_DIR = "data/conversations"
