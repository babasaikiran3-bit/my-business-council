"""Project-wide pytest fixtures with isolated application state."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Generator

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_BACKEND_MODULES = [
    "backend.paths",
    "backend.config",
    "backend.migrations",
    "backend.storage",
]


def _fresh_imports() -> None:
    for module_name in _BACKEND_MODULES:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
        else:
            importlib.import_module(module_name)


def _restore_home(monkeypatch: pytest.MonkeyPatch, previous: str | None) -> None:
    if previous is None:
        monkeypatch.delenv("COUNCIL_HOME", raising=False)
    else:
        monkeypatch.setenv("COUNCIL_HOME", previous)
    _fresh_imports()


@pytest.fixture
def temp_db(monkeypatch, tmp_path: Path) -> Generator[str, None, None]:
    """Fully migrated SQLite database isolated under ``tmp_path``."""
    previous = os.environ.get("COUNCIL_HOME")
    monkeypatch.setenv("COUNCIL_HOME", str(tmp_path))
    _fresh_imports()

    import backend.storage

    backend.storage.init_db()
    try:
        yield str(tmp_path / "council.db")
    finally:
        _restore_home(monkeypatch, previous)


@pytest.fixture
def temp_db_raw(monkeypatch, tmp_path: Path) -> Generator[str, None, None]:
    """Isolated database path without applying application migrations."""
    previous = os.environ.get("COUNCIL_HOME")
    monkeypatch.setenv("COUNCIL_HOME", str(tmp_path))
    _fresh_imports()
    try:
        yield str(tmp_path / "council.db")
    finally:
        _restore_home(monkeypatch, previous)
