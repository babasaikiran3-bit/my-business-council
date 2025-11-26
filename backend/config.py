"""Configuration for the LLM Council."""

import os
import json
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Config file path
CONFIG_FILE = Path("data/council_config.json")

# Default council configuration
_default_council_models = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]
_default_chairman_model = "google/gemini-3-pro-preview"

# Runtime configuration (mutable)
_council_config: Dict[str, Any] = {
    "council_models": _default_council_models.copy(),
    "chairman_model": _default_chairman_model,
    "custom_models": []  # User-added models
}


def _load_config():
    """Load configuration from file if exists."""
    global _council_config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
                _council_config["council_models"] = saved.get("council_models", _default_council_models)
                _council_config["chairman_model"] = saved.get("chairman_model", _default_chairman_model)
                _council_config["custom_models"] = saved.get("custom_models", [])
        except Exception as e:
            print(f"⚠️ Failed to load config: {e}")


def _save_config():
    """Save configuration to file."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(_council_config, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save config: {e}")


# Load config on module import
_load_config()


def get_council_config() -> Dict[str, Any]:
    """Get current council configuration."""
    return _council_config.copy()


def update_council_config(council_models: List[str] = None, chairman_model: str = None, custom_models: List[str] = None) -> Dict[str, Any]:
    """Update council configuration."""
    global _council_config
    if council_models is not None:
        _council_config["council_models"] = council_models
    if chairman_model is not None:
        _council_config["chairman_model"] = chairman_model
    if custom_models is not None:
        _council_config["custom_models"] = custom_models
    _save_config()
    return _council_config.copy()


# Properties for backward compatibility
@property
def COUNCIL_MODELS() -> List[str]:
    return _council_config["council_models"]


@property  
def CHAIRMAN_MODEL() -> str:
    return _council_config["chairman_model"]


# For direct imports (backward compat) - these are functions now
def get_council_models() -> List[str]:
    """Get current council models - always read from file for worker compatibility."""
    _load_config()  # Reload from file to get latest changes
    return _council_config["council_models"]


def get_chairman_model() -> str:
    """Get current chairman model - always read from file for worker compatibility."""
    _load_config()  # Reload from file to get latest changes
    return _council_config["chairman_model"]

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# Redis configuration for background jobs
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"

# Model pricing (USD per 1M tokens) - Updated from OpenRouter
# Used for estimated cost calculation (actual cost fetched from generation API)
MODEL_PRICING = {
    # Pricing from OpenRouter API (updated 2025-11-24)
    "openai/gpt-5.1": {"input": 1.25, "output": 10.00},
    "google/gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
    "anthropic/claude-sonnet-4.5": {"input": 3.00, "output": 15.00},
    "x-ai/grok-4": {"input": 3.00, "output": 15.00},
    "google/gemini-2.5-flash": {"input": 0.30, "output": 2.50},  # Used for title generation only
}

DEFAULT_PRICING = {"input": 1.00, "output": 3.00}  # Fallback for unknown models

def calculate_estimated_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calculate estimated cost based on token usage.
    This is an approximation - actual cost will be fetched from OpenRouter generation API.
    
    Args:
        model: Model identifier
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
    
    Returns:
        Estimated cost in USD
    """
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost
