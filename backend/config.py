"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv(override=True)


def _parse_csv(value: str | None) -> list[str]:
    """Parse comma-separated environment variables into a clean list."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


# Provider: "openrouter", "azure", "fireworks", "bedrock", or "mixed"
LLM_PROVIDER = os.getenv("LLM_COUNCIL_PROVIDER", "openrouter").lower()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Optional reasoning setting for the chairman model. OpenAI calls use "xhigh"
# for the extra-high reasoning tier.
CHAIRMAN_REASONING_EFFORT = os.getenv("CHAIRMAN_REASONING_EFFORT")

# Azure OpenAI settings
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
AZURE_OPENAI_DEPLOYMENTS = _parse_csv(
    os.getenv("AZURE_OPENAI_DEPLOYMENTS")
    or os.getenv("AZURE_OPENAI_DEPLOYMENT")
    or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
)

# Fireworks settings
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY") or os.getenv("FIREWORKS_AI_API_KEY")
FIREWORKS_BASE_URL = os.getenv(
    "FIREWORKS_BASE_URL",
    "https://api.fireworks.ai/inference/v1"
).rstrip("/")
FIREWORKS_MODELS = _parse_csv(
    os.getenv("FIREWORKS_MODELS")
    or os.getenv("FIREWORKS_MODEL")
)

# Amazon Bedrock settings
BEDROCK_REGION = (
    os.getenv("BEDROCK_REGION")
    or os.getenv("AWS_REGION")
    or os.getenv("AWS_DEFAULT_REGION")
    or "us-east-1"
)
BEDROCK_MODELS = _parse_csv(
    os.getenv("BEDROCK_MODELS")
    or os.getenv("BEDROCK_MODEL")
)

# Council members - OpenRouter model identifiers, Azure deployment names, or
# provider-prefixed mixed entries like "azure:gpt-5".
DEFAULT_OPENROUTER_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]
DEFAULT_FIREWORKS_MODELS = [
    "accounts/fireworks/models/glm-5p2",
]
DEFAULT_BEDROCK_MODELS = [
    "us.anthropic.claude-opus-4-8",
    "us.anthropic.claude-fable-5",
]

if LLM_PROVIDER == "mixed":
    COUNCIL_MODELS = _parse_csv(os.getenv("COUNCIL_MODELS"))
    if not COUNCIL_MODELS:
        COUNCIL_MODELS = [
            *(f"azure:{model}" for model in AZURE_OPENAI_DEPLOYMENTS),
            *(f"fireworks:{model}" for model in (FIREWORKS_MODELS or DEFAULT_FIREWORKS_MODELS)),
            *(f"bedrock:{model}" for model in (BEDROCK_MODELS or DEFAULT_BEDROCK_MODELS)),
        ]
    BEDROCK_CHAIRMAN_MODEL = os.getenv("BEDROCK_CHAIRMAN_MODEL")
    if BEDROCK_CHAIRMAN_MODEL and not BEDROCK_CHAIRMAN_MODEL.startswith("bedrock:"):
        BEDROCK_CHAIRMAN_MODEL = f"bedrock:{BEDROCK_CHAIRMAN_MODEL}"

    CHAIRMAN_MODEL = os.getenv("CHAIRMAN_MODEL") or BEDROCK_CHAIRMAN_MODEL or COUNCIL_MODELS[0]
    TITLE_MODEL = os.getenv("TITLE_MODEL", CHAIRMAN_MODEL)
elif LLM_PROVIDER == "azure" and AZURE_OPENAI_DEPLOYMENTS:
    COUNCIL_MODELS = AZURE_OPENAI_DEPLOYMENTS
    CHAIRMAN_MODEL = (
        os.getenv("AZURE_OPENAI_CHAIRMAN_DEPLOYMENT")
        or os.getenv("CHAIRMAN_MODEL")
        or AZURE_OPENAI_DEPLOYMENTS[0]
    )
    TITLE_MODEL = (
        os.getenv("AZURE_OPENAI_TITLE_DEPLOYMENT")
        or os.getenv("TITLE_MODEL")
        or CHAIRMAN_MODEL
    )
elif LLM_PROVIDER == "fireworks":
    COUNCIL_MODELS = _parse_csv(os.getenv("COUNCIL_MODELS")) or FIREWORKS_MODELS or DEFAULT_FIREWORKS_MODELS
    CHAIRMAN_MODEL = (
        os.getenv("FIREWORKS_CHAIRMAN_MODEL")
        or os.getenv("CHAIRMAN_MODEL")
        or COUNCIL_MODELS[0]
    )
    TITLE_MODEL = (
        os.getenv("FIREWORKS_TITLE_MODEL")
        or os.getenv("TITLE_MODEL")
        or CHAIRMAN_MODEL
    )
elif LLM_PROVIDER == "bedrock":
    COUNCIL_MODELS = _parse_csv(os.getenv("COUNCIL_MODELS")) or BEDROCK_MODELS or DEFAULT_BEDROCK_MODELS
    CHAIRMAN_MODEL = (
        os.getenv("BEDROCK_CHAIRMAN_MODEL")
        or os.getenv("CHAIRMAN_MODEL")
        or COUNCIL_MODELS[0]
    )
    TITLE_MODEL = (
        os.getenv("BEDROCK_TITLE_MODEL")
        or os.getenv("TITLE_MODEL")
        or CHAIRMAN_MODEL
    )
else:
    COUNCIL_MODELS = _parse_csv(os.getenv("COUNCIL_MODELS")) or DEFAULT_OPENROUTER_MODELS
    # Chairman model - synthesizes final response
    CHAIRMAN_MODEL = os.getenv("CHAIRMAN_MODEL", "google/gemini-3-pro-preview")
    TITLE_MODEL = os.getenv("TITLE_MODEL", "google/gemini-2.5-flash")

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
