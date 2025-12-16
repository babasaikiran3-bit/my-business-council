"""Configuration for Eternal Copilot."""

import os

from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# WorkOS Authentication Configuration
WORKOS_API_KEY = os.getenv("WORKOS_API_KEY")
WORKOS_CLIENT_ID = os.getenv("WORKOS_CLIENT_ID")
EMPLOYEE_EMAIL_DOMAIN = os.getenv("EMPLOYEE_EMAIL_DOMAIN", "eternal.ag")
ALLOWED_PARTNER_DOMAINS = os.getenv("ALLOWED_PARTNER_DOMAINS", "").split(",")
ALLOWED_PARTNER_DOMAINS = [d.strip() for d in ALLOWED_PARTNER_DOMAINS if d.strip()]

# Token cache TTL in seconds (45 seconds as per WORKOS.md)
TOKEN_CACHE_TTL = 45

# CORS allowed origins - comma-separated list
# Defaults to localhost:5173 and localhost:3000 for development
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if _allowed_origins_env:
    ALLOWED_ORIGINS = [origin.strip() for origin in _allowed_origins_env.split(",") if origin.strip()]
else:
    ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]

# Copilot models - list of OpenRouter model identifiers
COPILOT_MODELS = [
    "openai/gpt-5.2-pro",
    "google/gemini-3-pro-preview",
    "anthropic/claude-opus-4.5",
    "x-ai/grok-4",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# Prompt improver model - fast model for quick prompt enhancement
# Using the same model as chairman for reliability; can be changed to a faster model
PROMPT_IMPROVER_MODEL = "google/gemini-3-pro-preview"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
# Use /tmp for Vercel serverless functions, otherwise use local directory
IS_VERCEL = os.getenv("VERCEL", "false").lower() == "1" or os.getenv("VERCEL_ENV") is not None
if IS_VERCEL:
    DATA_DIR = "/tmp/conversations"
else:
    DATA_DIR = "data/conversations"
