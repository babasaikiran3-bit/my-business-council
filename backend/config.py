"""Configuration for the LLM Council.

Supports three provider modes:
1. 'openrouter': All models use OpenRouter API (default)
2. 'ollama': All models use local Ollama server
3. 'mixed': Prefix each model with provider (e.g., 'ollama:llama3.1:8b', 'openrouter:google/gemini-2.5-flash-lite')
"""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Provider configuration
# Valid values: 'openrouter', 'ollama', 'mixed'
# Default: 'openrouter' for backward compatibility
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")
print(f"LLM_PROVIDER set to: {LLM_PROVIDER}")
# Validate LLM_PROVIDER
VALID_PROVIDERS = ["openrouter", "ollama", "mixed"]
if LLM_PROVIDER not in VALID_PROVIDERS:
    raise ValueError(
        f"Invalid LLM_PROVIDER '{LLM_PROVIDER}'. Must be one of {VALID_PROVIDERS}"
    )

# OpenRouter API key (required for 'openrouter' and 'mixed' modes)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Ollama base URL (required for 'ollama' and 'mixed' modes)
# Default: http://localhost:11434
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Council members - adapts based on LLM_PROVIDER
#
# Examples:
# - openrouter mode: ["openai/gpt-5.1", "google/gemini-3-pro-preview"]
# - ollama mode: ["llama3.1:8b", "mistral:latest", "qwen2.5:3b"]
# - mixed mode: ["ollama:llama3.1:8b", "openrouter:google/gemini-2.5-flash-lite"]
if LLM_PROVIDER == "openrouter":
    # Original OpenRouter configuration (backward compatible)
    COUNCIL_MODELS = [
        "openai/gpt-5.1",
        "google/gemini-3-pro-preview",
        "anthropic/claude-sonnet-4.5",
        "x-ai/grok-4",
    ]
    # Original OpenRouter configuration (backward compatible)
    CHAIRMAN_MODEL = "google/gemini-3-pro-preview"
    TITLE_MODEL = "google/gemini-2.5-flash-lite"
elif LLM_PROVIDER == "ollama":
    # Local Ollama models
    COUNCIL_MODELS = [
        "mistral:latest",
        "qwen2.5:3b",
        "phi3:latest",
    ]
     # Local Ollama chairman
    CHAIRMAN_MODEL = "mistral:latest"
    TITLE_MODEL = "phi3:latest"
else:  # mixed mode
    # Mixed provider configuration with explicit prefixes
    COUNCIL_MODELS = [
        "ollama:phi3:latest",
        "ollama:mistral:latest",
        "openrouter:google/gemini-3-pro-preview",
        "openrouter:anthropic/claude-3.5-haiku",
    ]
    # Mixed mode chairman (can use either provider)
    CHAIRMAN_MODEL = "openrouter:google/gemini-3-pro-preview"
    TITLE_MODEL = "openrouter:google/gemini-2.5-flash-lite"


# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
