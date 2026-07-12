"""Shared test fixtures — isolated temp databases, no real providers.

Every fixture that needs a database sets ``COUNCIL_HOME`` to a unique temporary
directory *before* the backend modules are imported or reloaded, so paths are
always isolated.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Generator

# Ensure the project root is on sys.path (backend runs as `python -m backend.main`
# from the project root, so we simulate that here).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BACKEND_MODULES = [
    "backend.paths",
    "backend.config",
    "backend.migrations",
    "backend.storage",
]


def _fresh_imports():
    """Reload (or first-time import) backend modules in dependency order."""
    for modname in _BACKEND_MODULES:
        if modname in sys.modules:
            importlib.reload(sys.modules[modname])
        else:
            importlib.import_module(modname)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db(monkeypatch, tmp_path: Path) -> Generator[str, None, None]:
    """Isolated database in *tmp_path*, fully migrated via ``init_db()``.

    Sets ``COUNCIL_HOME`` so every data file (``.db``, config JSON, agent-cwd)
    lands under the temporary directory.  Reloads the backend modules so the
    new paths take effect, then runs ``init_db()`` which applies all pending
    migrations.
    """
    monkeypatch.setenv("COUNCIL_HOME", str(tmp_path))
    _fresh_imports()

    import backend.storage

    backend.storage.init_db()
    yield str(tmp_path / "council.db")


@pytest.fixture
def temp_db_raw(monkeypatch, tmp_path: Path) -> Generator[str, None, None]:
    """Like *temp_db* but WITHOUT running ``init_db()`` — the database file
    is created but contains no tables or migrations.  Use this when you need
    to test migration behaviour from a completely clean state.
    """
    monkeypatch.setenv("COUNCIL_HOME", str(tmp_path))
    _fresh_imports()
    yield str(tmp_path / "council.db")
