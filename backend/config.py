"""Configuration for Eternal Ops Control.

Environment Loading Priority:
1. ENV environment variable determines which .env file to load
2. Default: development (loads .env.development if exists, else .env)
3. Staging: ENV=staging (loads .env.staging)
4. Production: ENV=production (loads .env.production)

Usage:
    # Development (default)
    python -m backend.main

    # Staging
    ENV=staging python -m backend.main

    # Production
    ENV=production python -m backend.main
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Determine environment (default to development)
ENV = os.getenv("ENV", "development").lower()

# Validate environment
VALID_ENVIRONMENTS = ("development", "staging", "production")
if ENV not in VALID_ENVIRONMENTS:
    print(f"⚠️  Warning: Invalid ENV='{ENV}'. Using 'development'. Valid options: {VALID_ENVIRONMENTS}")
    ENV = "development"

# Load environment-specific .env file
# Priority: .env.{environment} -> .env (fallback for development only)
project_root = Path(__file__).parent.parent
env_file = project_root / f".env.{ENV}"
fallback_env_file = project_root / ".env"

if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded environment: {ENV} (from {env_file.name})")
elif ENV == "development" and fallback_env_file.exists():
    load_dotenv(fallback_env_file)
    print(f"✅ Loaded environment: {ENV} (from .env fallback)")
else:
    # Try loading .env anyway in case it has some defaults
    load_dotenv()
    print(f"⚠️  No .env.{ENV} file found. Using environment variables only.")

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Supabase Configuration
# Project: prod-eternal-ops-control (vthibdgqnxfbjrscxdlf) in eu-west-1
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://vthibdgqnxfbjrscxdlf.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

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

# Typesense Cloud Configuration
# Get these values from Typesense Cloud dashboard: https://cloud.typesense.org/
TYPESENSE_HOST = os.getenv("TYPESENSE_HOST", "")  # e.g., "xyz.a1.typesense.net"
TYPESENSE_PORT = os.getenv("TYPESENSE_PORT", "443")
TYPESENSE_PROTOCOL = os.getenv("TYPESENSE_PROTOCOL", "https")
TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY", "")  # Admin API key for indexing
TYPESENSE_SEARCH_ONLY_KEY = os.getenv("TYPESENSE_SEARCH_ONLY_KEY", "")  # Search-only key for scoped keys

# Data directory for conversation storage
# Use /tmp for Vercel serverless functions, otherwise use local directory
IS_VERCEL = os.getenv("VERCEL", "false").lower() == "1" or os.getenv("VERCEL_ENV") is not None
if IS_VERCEL:
    DATA_DIR = "/tmp/conversations"
else:
    DATA_DIR = "data/conversations"
