"""Configuration for the LLM Council.

Supports multiple LLM providers via LiteLLM. Set API keys in .env for the
providers you want to use directly. If a direct key isn't available for a
model's provider, falls back to OpenRouter.

Supported env vars:
    OPENAI_API_KEY      - OpenAI models (gpt-4o, gpt-5.1, etc.)
    ANTHROPIC_API_KEY   - Anthropic models (claude-sonnet-4.5, etc.)
    GEMINI_API_KEY      - Google Gemini models (gemini-3-pro-preview, etc.)
    XAI_API_KEY         - xAI models (grok-4, etc.)
    DEEPSEEK_API_KEY    - DeepSeek models
    OPENROUTER_API_KEY  - OpenRouter (fallback for any model)
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Provider routing
# ---------------------------------------------------------------------------

# Map litellm provider prefix -> env var name
PROVIDER_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "xai": "XAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}

# Map litellm provider prefix -> OpenRouter provider prefix
# (only needed where they differ)
LITELLM_TO_OPENROUTER_PROVIDER = {
    "gemini": "google",
    "xai": "x-ai",
}

# OpenRouter fallback key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ---------------------------------------------------------------------------
# Council configuration
# ---------------------------------------------------------------------------

# Council members - use litellm model identifiers (provider/model-name)
# Examples:
#   "openai/gpt-5.1"              -> uses OPENAI_API_KEY directly, or OpenRouter
#   "gemini/gemini-3-pro-preview"  -> uses GEMINI_API_KEY directly, or OpenRouter
#   "anthropic/claude-sonnet-4.5"  -> uses ANTHROPIC_API_KEY directly, or OpenRouter
#   "xai/grok-4"                   -> uses XAI_API_KEY directly, or OpenRouter
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "gemini/gemini-3-pro-preview",
    "openai/gpt-5.2",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "gemini/gemini-3-pro-preview"

# Model used for lightweight tasks (title generation, etc.)
UTILITY_MODEL = "gemini/gemini-3-flash-preview"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------


def get_provider(model: str) -> str:
    """Extract the provider prefix from a litellm model identifier."""
    if "/" in model:
        return model.split("/")[0]
    return "openai"  # bare model names default to OpenAI


def has_direct_api_key(model: str) -> bool:
    """Check if a direct API key exists for the model's provider."""
    provider = get_provider(model)
    env_var = PROVIDER_KEY_MAP.get(provider)
    if env_var:
        return bool(os.getenv(env_var))
    return False


def resolve_model(model: str) -> str:
    """Resolve a model identifier to the litellm-compatible string to use.

    - If a direct API key exists for the provider, returns the model as-is
      (litellm will use the native API).
    - Otherwise, prepends 'openrouter/' and converts the provider prefix to
      OpenRouter's naming convention.
    - Raises ValueError if no usable key is found.
    """
    if has_direct_api_key(model):
        return model

    if OPENROUTER_API_KEY:
        provider = get_provider(model)
        model_name = model.split("/", 1)[1] if "/" in model else model
        or_provider = LITELLM_TO_OPENROUTER_PROVIDER.get(provider, provider)
        return f"openrouter/{or_provider}/{model_name}"

    # No key available
    provider = get_provider(model)
    expected_var = PROVIDER_KEY_MAP.get(provider, f"{provider.upper()}_API_KEY")
    raise ValueError(
        f"No API key found for model '{model}'. "
        f"Set {expected_var} for direct access or OPENROUTER_API_KEY as a fallback "
        f"in your .env file."
    )


def print_routing_info():
    """Print which providers will be used (helpful at startup)."""
    print("\n=== LLM Council - Provider Routing ===")
    all_models = list(set(COUNCIL_MODELS + [CHAIRMAN_MODEL, UTILITY_MODEL]))
    for model in sorted(all_models):
        try:
            resolved = resolve_model(model)
            route = "direct API" if resolved == model else "via OpenRouter"
            print(f"  {model:45s} -> {route}")
        except ValueError as e:
            print(f"  {model:45s} -> ERROR: {e}")
    print("=" * 43 + "\n")
