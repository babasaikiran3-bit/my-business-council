"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers
# Using free/cheaper models that work with current API credits
# Note: Free models may have rate limits - if you see 429 errors, consider using paid models
COUNCIL_MODELS = [
    "mistralai/mistral-7b-instruct:free",
    "openai/gpt-4o-mini",
    "mistralai/mistral-7b-instruct:free",  # Using twice since Llama has rate limits
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "openai/gpt-4o-mini"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
