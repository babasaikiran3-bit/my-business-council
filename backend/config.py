"""Configuration for the LLM Council."""

import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenRouter API endpoint
OPENROUTER_API_URL = os.getenv(
    "OPENROUTER_API_URL",
    "https://openrouter.ai/api/v1/chat/completions"
)

# Data directory for conversation storage
DATA_DIR = os.getenv("DATA_DIR", "data/conversations")

# Log level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Default council members - can be overridden via COUNCIL_MODELS env var
_DEFAULT_COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# Default chairman model - can be overridden via CHAIRMAN_MODEL env var
_DEFAULT_CHAIRMAN_MODEL = "google/gemini-3-pro-preview"


def _parse_model_list(env_value: str) -> List[str]:
    """
    Parse comma-separated model list from environment variable.

    Args:
        env_value: Comma-separated string of model identifiers

    Returns:
        List of model identifiers with whitespace stripped
    """
    return [model.strip() for model in env_value.split(",") if model.strip()]


# Council members - list of OpenRouter model identifiers
# Can be overridden via environment variable: COUNCIL_MODELS="model1,model2,model3"
_council_models_env = os.getenv("COUNCIL_MODELS")
COUNCIL_MODELS = (
    _parse_model_list(_council_models_env)
    if _council_models_env
    else _DEFAULT_COUNCIL_MODELS
)

# Chairman model - synthesizes final response
# Can be overridden via environment variable: CHAIRMAN_MODEL="model-name"
CHAIRMAN_MODEL = os.getenv("CHAIRMAN_MODEL", _DEFAULT_CHAIRMAN_MODEL)


def validate_config():
    """
    Validate configuration.

    This is called when actually using the council, not at import time.
    This allows CLI --help and other commands to work without API key.
    """
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable is required. "
            "Please set it in your .env file or environment."
        )

    if not COUNCIL_MODELS:
        raise ValueError(
            "COUNCIL_MODELS must contain at least one model. "
            "Check your configuration or COUNCIL_MODELS environment variable."
        )

    if not CHAIRMAN_MODEL:
        raise ValueError(
            "CHAIRMAN_MODEL is required. "
            "Check your configuration or CHAIRMAN_MODEL environment variable."
        )
