"""Configuración del LLM Council.

El universo de modelos vive en models_registry.py; la selección activa (members/chairman)
se persiste vía council_config.py. Acá quedan solo constantes globales y re-exports cómodos.

Los paths de datos se definen de forma determinista en paths.py (absolutos, con override
por variables de entorno).  Se re-exportan acá para mantener compatibilidad con código
existente que importa ``from .config import DB_PATH, ...``.
"""

from .models_registry import (  # noqa: F401  (re-export)
    REGISTRY,
    DEFAULT_MEMBERS,
    DEFAULT_CHAIRMAN,
    TITLE_MODEL,
)

# Re-export de paths deterministas (ver backend/paths.py).
from .paths import (  # noqa: F401  (re-export)
    DB_PATH,
    DATA_DIR,
    COUNCIL_CONFIG_PATH,
    AGENT_CWD,
)
