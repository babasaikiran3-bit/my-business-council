"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Provider selection: "openrouter" (default) or "local"
PROVIDER = os.getenv("COUNCIL_PROVIDER", "openrouter").strip().lower()

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# Custom models configuration (OpenAI-compatible endpoints)
# Format: { "model_id": { "api_url": "...", "api_key": "..." } }
# Example for a local Ollama OpenAI-compatible endpoint:
# CUSTOM_MODELS = {
#     "ollama/llama3": {
#         "api_url": "http://localhost:11434/v1/chat/completions",
#         "api_key": "ollama"  # often ignored by local servers but required by some clients
#     }
# }
CUSTOM_MODELS = {}

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# ---------- Local (Ollama) settings ----------
# Base URL for the Ollama daemon
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()

# Comma-separated list of local model names (e.g. "nemotron,nemotron9b,nemotron12b")
_local_models_env = os.getenv("LOCAL_MODELS")
if _local_models_env:
    LOCAL_MODELS = [m.strip() for m in _local_models_env.split(",") if m.strip()]
else:
    # Defaults based on models you installed with Ollama
    LOCAL_MODELS = ["nemotron", "nemotron9b", "nemotron12b"]

# Chairman model to use when PROVIDER == "local"
CHAIRMAN_LOCAL_MODEL = os.getenv("CHAIRMAN_LOCAL_MODEL")
if not CHAIRMAN_LOCAL_MODEL:
    if "nemotron12b" in LOCAL_MODELS:
        CHAIRMAN_LOCAL_MODEL = "nemotron12b"
    elif LOCAL_MODELS:
        CHAIRMAN_LOCAL_MODEL = LOCAL_MODELS[0]
    else:
        CHAIRMAN_LOCAL_MODEL = "nemotron"

# Keep at least this much RAM free for the OS/apps (in GiB)
COUNCIL_MEM_RESERVE_GB = float(os.getenv("COUNCIL_MEM_RESERVE_GB", "6"))

# Hard cap on number of concurrent local model runs (optional).
# If unset, adaptive guard uses memory budget alone.
COUNCIL_MAX_PARALLEL_LOCAL = os.getenv("COUNCIL_MAX_PARALLEL_LOCAL")
COUNCIL_MAX_PARALLEL_LOCAL = int(COUNCIL_MAX_PARALLEL_LOCAL) if COUNCIL_MAX_PARALLEL_LOCAL else None

# Enable/disable adaptive resource guard
COUNCIL_ADAPTIVE_RESOURCE_GUARD = os.getenv("COUNCIL_ADAPTIVE_RESOURCE_GUARD", "1").strip().lower() in {"1", "true", "yes", "on"}

# Per-call timeout (seconds) for local model requests
COUNCIL_LOCAL_TIMEOUT_SEC = float(os.getenv("COUNCIL_LOCAL_TIMEOUT_SEC", "180"))
