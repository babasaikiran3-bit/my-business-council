"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Tuzi API key
TUZI_API_KEY = os.getenv("TUZI_API_KEY")

# Council members - list of model identifiers
COUNCIL_MODELS = [
    "gpt-5.1",
    "gemini-3-pro-preview",
    "claude-opus-4-5-20251101",
    "grok-4.1",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "gemini-3-pro-preview"

# Tuzi API endpoint (OpenAI compatible)
TUZI_API_URL = "https://api.tu-zi.com/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
