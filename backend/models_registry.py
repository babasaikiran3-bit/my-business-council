"""Registro declarativo de modelos del consejo.

El REGISTRY es el *universo* de modelos posibles. Qué subconjunto participa en el
consejo se decide en data/council_config.json (ver council_config.py). Sumar un modelo
= agregar una entrada acá; no se toca lógica.

Tres clases de transporte (resueltas en providers.py):
  - cli_native      : binario agéntico propio (claude / codex / agy). Ojos y manos.
  - anthropic_agent : Claude Code apuntado a un endpoint Anthropic-compatible
                      (ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN + ANTHROPIC_MODEL).
                      Ojos y manos. Cubre DeepSeek (claude-ds) y todo aiapi.world (GLM...).
  - openai_api      : POST REST OpenAI-compatible. Ciego (sin tools). Títulos / Q&A rápido.
"""

import os

HOME = os.path.expanduser("~")

# Endpoint Anthropic-compatible de aiapi.world (sin /v1). Una sola key abre 100+ modelos.
AIAPI_BASE = "https://aiapi.world"
AIAPI_KEY_FILE = f"{HOME}/.aiapi_key"

REGISTRY = {
    # --- por suscripción (CLI nativo, costo flat) ---
    "claude": {"transport": "cli_native", "bin": "claude", "label": "Claude (Fable 5)"},
    "codex":  {"transport": "cli_native", "bin": "codex",  "label": "Codex (gpt-5.5)"},
    "gemini": {"transport": "cli_native", "bin": "agy",    "label": "Gemini 3.5 Pro"},

    # --- DeepSeek como agente Claude Code (ojos y manos) ---
    "deepseek": {
        "transport": "anthropic_agent",
        "label": "DeepSeek V4 Pro",
        "base": "https://api.deepseek.com/anthropic",
        "key_file": f"{HOME}/.deepseek_key",
        "model": "deepseek-v4-pro",
        "small_model": "deepseek-v4-flash",
        "config_dir": f"{HOME}/.claude-ds",
    },

    # --- modelos extra vía aiapi.world (una key, ojos y manos) ---
    "glm": {
        "transport": "anthropic_agent",
        "label": "GLM 5.2",
        "base": AIAPI_BASE,
        "key_file": AIAPI_KEY_FILE,
        "model": "glm-5.2",
        "small_model": "glm-5.2",
        "config_dir": f"{HOME}/.claude-aiapi",
    },
    "kimi": {
        "transport": "anthropic_agent",
        "label": "Kimi K2.7 Code",
        "base": AIAPI_BASE,
        "key_file": AIAPI_KEY_FILE,
        "model": "kimi-k2.7-code",
        "small_model": "kimi-k2.7-code",
        "config_dir": f"{HOME}/.claude-aiapi",
    },
    "grok": {
        "transport": "anthropic_agent",
        "label": "Grok 4",
        "base": AIAPI_BASE,
        "key_file": AIAPI_KEY_FILE,
        "model": "grok-4",
        "small_model": "grok-4",
        "config_dir": f"{HOME}/.claude-aiapi",
    },

    # --- ciego, OpenAI-compatible (solo títulos) ---
    "deepseek-flash": {
        "transport": "openai_api",
        "label": "DeepSeek V4 Flash",
        "base": "https://api.deepseek.com/v1",
        "key_file": f"{HOME}/.deepseek_key",
        "model": "deepseek-v4-flash",
    },
}

# Default del consejo: los que tienen credenciales estables hoy. GLM/Kimi/Grok se activan
# desde el panel cuando exista ~/.aiapi_key.
DEFAULT_MEMBERS = ["claude", "codex", "gemini", "deepseek"]
DEFAULT_CHAIRMAN = "claude"

# Modelo rápido/barato para títulos (no necesita ojos ni manos).
TITLE_MODEL = "deepseek-flash"


def get(model_id: str) -> dict:
    """Devuelve la spec de un modelo o lanza KeyError."""
    return REGISTRY[model_id]


def exists(model_id: str) -> bool:
    return model_id in REGISTRY
