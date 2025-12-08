"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# Provider Configuration
# ============================================================================

# Default provider when model identifier has no prefix (e.g., "gpt-4" instead of "openrouter:gpt-4")
# Options: "openrouter", "ollama", "lmstudio"
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "openrouter")

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Ollama server configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# LMStudio server configuration
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1/chat/completions")

# ============================================================================
# Council Configuration
# ============================================================================

# COUNCIL_MODELS: List of models that will participate in the council
#
# Model identifier format:
#   - Prefixed: "provider:model" (e.g., "ollama:llama2", "openrouter:gpt-4")
#   - Simple: "model" (uses DEFAULT_PROVIDER)
#
# Examples:
#   - All OpenRouter: ["openai/gpt-4", "anthropic/claude-3-sonnet"]
#   - All Ollama: ["ollama:llama2", "ollama:mistral"]
#   - Mixed: ["ollama:llama2", "openrouter:gpt-4", "lmstudio:mistral"]
#
# You can mix providers freely for maximum flexibility!

COUNCIL_MODELS = [
    # Example: All cloud models (requires OPENROUTER_API_KEY)
    "openai/gpt-4o",
    "google/gemini-2.0-flash-exp",
    "anthropic/claude-sonnet-4",
    "x-ai/grok-3",

    # Example: All local models (requires Ollama running)
    # "ollama:llama2:13b-chat",
    # "ollama:mistral:7b-instruct",
    # "ollama:codellama:34b-instruct",

    # Example: Mixed mode
    # "ollama:llama2:13b-chat",
    # "openrouter:gpt-4o",
    # "lmstudio:mistral",
]

# CHAIRMAN_MODEL: Model that synthesizes the final response
# Can be from any provider, independent of council models
CHAIRMAN_MODEL = "google/gemini-2.0-flash-exp"

# CONVERSATION_TITLE_MODEL: Fast model for generating conversation titles
# Recommend using a fast/cheap model for this task
CONVERSATION_TITLE_MODEL = "google/gemini-2.0-flash-exp"

# ============================================================================
# Legacy Configuration (for backward compatibility)
# ============================================================================
# These are kept for reference but not used in the new provider-based system

# Legacy cloud models
COUNCIL_CLOUD_MODELS = [
    "openai/gpt-4o",
    "google/gemini-2.0-flash-exp",
    "anthropic/claude-sonnet-4",
    "x-ai/grok-3",
]
CHAIRMAN_CLOUD_MODEL = "google/gemini-2.0-flash-exp"
CONVERSATION_CLOUD_MODEL = "google/gemini-2.0-flash-exp"

# Legacy local models
COUNCIL_LOCAL_MODELS = [
    "llama2:13b-chat",
    "mistral:7b-instruct",
    "codellama:34b-instruct",
]
CHAIRMAN_LOCAL_MODEL = "mistral:7b-instruct"
CONVERSATION_LOCAL_MODEL = "mistral"

# Legacy API URLs
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# ============================================================================
# Storage Configuration
# ============================================================================

# Data directory for conversation storage
DATA_DIR = "data/conversations"
