"""Configuración activa del consejo: salud de modelos + persistencia de selección.

- El REGISTRY (models_registry) es el universo de modelos.
- Acá se decide qué subconjunto está activo y quién es chairman, persistido en JSON.
- health() chequea disponibilidad por existencia de binario/key (sin ping de red).
"""

import os
import json
import shutil
from typing import Dict, Any, List

from .models_registry import REGISTRY, DEFAULT_MEMBERS, DEFAULT_CHAIRMAN
from .config import COUNCIL_CONFIG_PATH


def health(model_id: str) -> Dict[str, Any]:
    """¿El modelo está usable? Chequea binario (cli_native) o key_file (resto).

    Returns: {"available": bool, "reason": str|None}
    """
    spec = REGISTRY.get(model_id)
    if spec is None:
        return {"available": False, "reason": "no existe en el registro"}

    transport = spec["transport"]
    if transport == "cli_native":
        bin_name = spec["bin"]
        if shutil.which(bin_name) or os.path.exists(os.path.expanduser(f"~/.local/bin/{bin_name}")):
            return {"available": True, "reason": None}
        return {"available": False, "reason": f"falta el binario «{bin_name}»"}

    # anthropic_agent / openai_api → necesitan key_file
    key_file = os.path.expanduser(spec.get("key_file", ""))
    if key_file and os.path.exists(key_file):
        return {"available": True, "reason": None}
    return {"available": False, "reason": f"falta {spec.get('key_file', 'la API key')}"}


def _default_config() -> Dict[str, Any]:
    return {"members": list(DEFAULT_MEMBERS), "chairman": DEFAULT_CHAIRMAN}


def load_config() -> Dict[str, Any]:
    """Carga la config persistida; si no existe, devuelve (y persiste) el default.

    Filtra miembros que ya no existan o que no estén disponibles, para no romper un
    debate por un modelo sin credenciales.
    """
    path = COUNCIL_CONFIG_PATH
    if os.path.exists(path):
        try:
            with open(path) as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError):
            cfg = _default_config()
    else:
        cfg = _default_config()
        save_config(cfg)

    # Saneo: solo miembros existentes y disponibles
    members = [m for m in cfg.get("members", []) if REGISTRY.get(m) and health(m)["available"]]
    if not members:
        members = [m for m in DEFAULT_MEMBERS if health(m)["available"]]

    chairman = cfg.get("chairman", DEFAULT_CHAIRMAN)
    if chairman not in members:
        chairman = members[0] if members else DEFAULT_CHAIRMAN

    return {"members": members, "chairman": chairman}


def save_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Persiste la config en data/council_config.json. Devuelve lo guardado."""
    os.makedirs(os.path.dirname(COUNCIL_CONFIG_PATH), exist_ok=True)
    data = {"members": list(cfg.get("members", [])), "chairman": cfg.get("chairman")}
    with open(COUNCIL_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)
    return data


def validate_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Valida una config entrante (del PUT). Lanza ValueError si es inválida."""
    members = cfg.get("members", [])
    if not isinstance(members, list) or not members:
        raise ValueError("members debe ser una lista no vacía")
    for m in members:
        if m not in REGISTRY:
            raise ValueError(f"modelo desconocido: {m}")
        h = health(m)
        if not h["available"]:
            raise ValueError(f"modelo «{m}» no disponible: {h['reason']}")
    chairman = cfg.get("chairman")
    if chairman not in members:
        raise ValueError("el chairman debe ser uno de los members")
    return {"members": members, "chairman": chairman}


def list_models() -> Dict[str, Any]:
    """Universo de modelos + salud + si están activos. Para GET /api/models.

    Nunca expone keys: solo el bool `available` y el motivo.
    """
    cfg = load_config()
    active = set(cfg["members"])
    models: List[Dict[str, Any]] = []
    for model_id, spec in REGISTRY.items():
        h = health(model_id)
        models.append({
            "id": model_id,
            "label": spec.get("label", model_id),
            "transport": spec["transport"],
            "model": spec.get("model"),
            "available": h["available"],
            "reason": h["reason"],
            "active": model_id in active,
            "title_only": model_id == "deepseek-flash",
        })
    return {"chairman": cfg["chairman"], "members": cfg["members"], "models": models}
