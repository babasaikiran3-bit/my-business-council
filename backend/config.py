"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Individual provider API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Council members - format: "provider/model"
COUNCIL_MODELS = [
    "openai/gpt-5.2",
    "google/gemini-3-pro-preview",  # Latest Gemini model
    "anthropic/claude-sonnet-4-5",
]

# Chairman model - synthesizes final response
# CHAIRMAN_MODEL = "google/gemini-3-pro-preview"
CHAIRMAN_MODEL = "anthropic/claude-sonnet-4-5"

# Provider API endpoints
PROVIDER_ENDPOINTS = {
    "openai_chat": "https://api.openai.com/v1/chat/completions",
    "openai_responses": "https://api.openai.com/v1/responses",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "google": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
}

# Models that require the Responses API (not Chat Completions)
OPENAI_RESPONSES_MODELS = ["gpt-5.2-pro", "gpt-5.2", "o3", "o4-mini"]

# Data directory for conversation storage
DATA_DIR = "data/conversations"
