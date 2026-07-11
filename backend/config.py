"""Configuración del LLM Council.

El universo de modelos vive en models_registry.py; la selección activa (members/chairman)
se persiste vía council_config.py. Acá quedan solo constantes globales y re-exports cómodos.
"""

from .models_registry import (  # noqa: F401  (re-export)
    REGISTRY,
    DEFAULT_MEMBERS,
    DEFAULT_CHAIRMAN,
    TITLE_MODEL,
)

# Directorio de almacenamiento de conversaciones (JSON legacy; usado por la migración).
DATA_DIR = "data/conversations"

# Base de datos SQLite (almacenamiento principal de conversaciones).
DB_PATH = "data/council.db"

# Archivo de configuración del consejo (members + chairman activos).
COUNCIL_CONFIG_PATH = "data/council_config.json"
