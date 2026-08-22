"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Provider registry: endpoint + the env var holding that provider's key.
# Every provider except Anthropic exposes an OpenAI-compatible
# /chat/completions endpoint, so they share one request/response shape.
PROVIDERS = {
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key_env": "OPENAI_API_KEY",
    },
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "key_env": "ANTHROPIC_API_KEY",
    },
    "google": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key_env": "GEMINI_API_KEY",
    },
    "x-ai": {
        "url": "https://api.x.ai/v1/chat/completions",
        "key_env": "XAI_API_KEY",
    },
}

# Council members - "<provider>/<model>". Provider must be a key in PROVIDERS.
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3.1-pro-preview",
    "anthropic/claude-opus-5",
    "x-ai/grok-4",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3.1-pro-preview"

# Anthropic requires max_tokens on every request; the others default it.
ANTHROPIC_MAX_TOKENS = 16000
ANTHROPIC_VERSION = "2023-06-01"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
