"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

COUNCIL_MODELS = [
    "openrouter/hunter-alpha",
    "stepfun/step-3.5-flash:free",
    "arcee-ai/trinity-large-preview:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

CHAIRMAN_MODEL = "stepfun/step-3.5-flash:free"

# API endpoint
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")

# Data directory for conversation storage
DATA_DIR = "data/conversations"
