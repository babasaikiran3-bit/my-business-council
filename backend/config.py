"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")

# Provider configurations
PROVIDERS = {
    "openai": {
        "council_models": [
            "gpt-4o",
            "gpt-5-mini",
            "gpt-5-nano"
        ],
        "chairman": "gpt-5.2",
        "transport": "http",
        "endpoint": "https://api.openai.com/v1/chat/completions"
    },
    "gemini": {
        "council_models": [
            "models/gemini-2.5-flash",
            "models/gemini-3-pro-preview",
            "models/gemini-2.0-flash"
        ],
        "chairman": "models/gemini-2.5-pro",
        "transport": "http",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    },
    "claude": {
        "council_models": [
            "claude-sonnet-4.5",
            "claude-sonnet-4",
            "claude-haiku-4.5"
        ],
        "chairman": "claude-opus-4.5",
        "transport": "http",
        "endpoint": "https://api.anthropic.com/v1/messages"
    },
    "cerebras": {
        "council_models": [
            "llama-3.3-70b",
            "llama3.1-8b",
            "qwen-3-32b"
        ],
        "chairman": "llama-3.3-70b",
        "transport": "http",
        "endpoint": "https://api.cerebras.ai/v1/chat/completions"
    }
}

# Data directory for conversation storage
DATA_DIR = "data/conversations"
