"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Active provider for council orchestration ("api" or "ollama").
# "openrouter" remains accepted as a backwards-compatible alias.
PROVIDER = os.getenv("PROVIDER", "api").strip().lower()
if PROVIDER == "openrouter":
    PROVIDER = "api"

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# --- Council composition ---
# For Ollama: every distinct model tag here means Ollama has to swap the
# resident model between calls unless you've configured it to keep several
# loaded at once (needs enough RAM/VRAM for all of them simultaneously).
# If things are slow, the first thing to try is dropping this to ONE model
# used for every role (council members, evaluators, chairman) — that keeps
# a single model resident for the whole request and removes reload latency
# entirely, at the cost of losing "diversity of models" in the panel.
def _model_list(name: str, default: str) -> list[str]:
    return [m.strip() for m in os.getenv(name, default).split(",") if m.strip()]


if PROVIDER == "ollama":
    COUNCIL_MODELS = _model_list(
        "OLLAMA_COUNCIL_MODELS", "llama3.2:3b,qwen3.5:2b,phi4-mini:latest"
    )
    CHAIRMAN_MODEL = os.getenv("OLLAMA_CHAIRMAN_MODEL", "phi4-mini:latest").strip()
    JUDGE_MODELS = _model_list(
        "OLLAMA_JUDGE_MODELS", ",".join(COUNCIL_MODELS)
    )
elif PROVIDER == "api":
    COUNCIL_MODELS = _model_list(
        "API_COUNCIL_MODELS",
        "openai/gpt-5.1,google/gemini-3-pro-preview,anthropic/claude-sonnet-4.5,x-ai/grok-4",
    )
    CHAIRMAN_MODEL = os.getenv(
        "API_CHAIRMAN_MODEL", "google/gemini-3-pro-preview"
    ).strip()
    JUDGE_MODELS = _model_list("API_JUDGE_MODELS", ",".join(COUNCIL_MODELS))
else:
    COUNCIL_MODELS = []
    CHAIRMAN_MODEL = ""
    JUDGE_MODELS = []

# Keep these names available for callers that imported the old constants.
if PROVIDER == "ollama":
    OLLAMA_COUNCIL_MODELS = COUNCIL_MODELS
    OLLAMA_CHAIRMAN_MODEL = CHAIRMAN_MODEL

# Skip the strict multi-field JSON critique schema on local models and use
# short plain-text critiques + a shorter synthesis prompt instead. Small
# (<7B) local models are unreliable at multi-field JSON across several
# response labels — when parsing fails, that evaluator's input silently
# becomes empty, which quietly starves stage 3 of anything to work with.
COUNCIL_LITE_MODE = (
    os.getenv("COUNCIL_LITE_MODE", "true" if PROVIDER == "ollama" else "false")
    .strip()
    .lower()
    == "true"
)

# Optional title-generation model. If not set, falls back to provider defaults.
TITLE_MODEL = os.getenv(
    "TITLE_MODEL",
    "google/gemini-2.5-flash" if PROVIDER == "api" else CHAIRMAN_MODEL,
).strip()

# OpenRouter API endpoint
OPENROUTER_API_URL = os.getenv(
    "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
)

# --- Ollama-specific tuning ---
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat")

# Ollama enables "thinking" by default for models that support it (Qwen3.x,
# DeepSeek-R1, etc). That reasoning trace eats into num_predict and can leave
# the visible response empty or truncated, on top of just being slower.
# Your provider code needs to actually send this — see note below.
OLLAMA_THINK = os.getenv("OLLAMA_THINK", "false").strip().lower() == "true"

# Keep the model resident between calls instead of Ollama's default ~5-minute
# unload. Matters a lot here since the same model gets called multiple times
# per turn (stage1 -> stage2 -> stage3).
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")

# Cap generation length so critique/synthesis calls can't ramble forever.
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))

# Per-call timeout (seconds) so a stuck local model doesn't hang the request
# indefinitely.
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

# Local, dependency-free retrieval configuration.
RAG_ENABLED = os.getenv("RAG_ENABLED", "false").strip().lower() == "true"
RAG_DOCUMENTS_DIR = os.getenv("RAG_DOCUMENTS_DIR", "data/documents")
RAG_TOP_K = max(1, int(os.getenv("RAG_TOP_K", "3")))
RAG_CHUNK_SIZE = max(100, int(os.getenv("RAG_CHUNK_SIZE", "800")))
RAG_CHUNK_OVERLAP = max(0, int(os.getenv("RAG_CHUNK_OVERLAP", "100")))

# Short-term conversation memory limits. Internal deliberation is never included.
CONTEXT_MAX_MESSAGES = max(0, int(os.getenv("CONTEXT_MAX_MESSAGES", "6")))
CONTEXT_MAX_CHARS = max(0, int(os.getenv("CONTEXT_MAX_CHARS", "12000")))

# Data directory for conversation storage
DATA_DIR = "data/conversations"


def validate_configuration() -> None:
    """Fail early with an actionable message when provider configuration is invalid."""
    if PROVIDER not in {"api", "ollama"}:
        raise ValueError("PROVIDER must be 'api' or 'ollama'.")
    if not COUNCIL_MODELS:
        raise ValueError("At least one council model must be configured.")
    if not CHAIRMAN_MODEL:
        raise ValueError("A chairman model must be configured.")
    if RAG_CHUNK_OVERLAP >= RAG_CHUNK_SIZE:
        raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE.")
    if CONTEXT_MAX_MESSAGES < 0 or CONTEXT_MAX_CHARS < 0:
        raise ValueError("Conversation context limits cannot be negative.")
    if CONTEXT_MAX_MESSAGES == 0 and CONTEXT_MAX_CHARS == 0:
        raise ValueError("At least one conversation context limit must be positive.")
    if PROVIDER == "api" and not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY is required when PROVIDER=api. "
            "Use PROVIDER=ollama for local-only operation."
        )