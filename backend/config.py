"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - diverse providers for balanced evaluation
COUNCIL_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    # "google/gemma-3-27b-it:free"
    "x-ai/grok-4.1-fast:free",
    "openai/gpt-oss-20b:free",
    # "nvidia/nemotron-nano-12b-v2-vl:free",
    # "alibaba/tongyi-deepresearch-30b-a3b:free",
    # "qwen/qwen3-235b-a22b:free",
    # "mistralai/mistral-7b-instruct:free"
]

# Chairman model - synthesizes final response (not used in evaluation mode)
CHAIRMAN_MODEL = "google/gemini-2.0-flash-exp:free"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
