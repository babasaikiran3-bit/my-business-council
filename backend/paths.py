"""Deterministic application paths — absolute, overridable, pathlib-based.

Every internal data path derives from ``COUNCIL_HOME`` (defaults to
``<project_root>/data``).  Individual paths may also be overridden explicitly
via environment variables so that tests and deployments can point to isolated
locations without touching code.

All path values are resolved to absolute paths (``expanduser`` +
``resolve``) so they are deterministic regardless of the working
directory.  The one exception is the SQLite special name ``:memory:``,
which is preserved as-is so that in-memory databases work.

Environment variables
---------------------
COUNCIL_HOME
    Root directory for ALL runtime data (database, config, agent-cwd, legacy
    JSON conversations).  Default: ``<project_root>/data``.  Relative values
    are resolved against the current working directory; ``~`` is expanded.

COUNCIL_DB_PATH
    Path to the SQLite database file.  May be a filesystem path (resolved to
    absolute) or the special value ``:memory:`` for an in-memory database.
    Overrides the ``COUNCIL_HOME``-based default.

COUNCIL_DATA_DIR
    Legacy JSON conversations directory (used only by the JSON→SQLite
    migration).  Resolved to absolute.  Overrides the ``COUNCIL_HOME``-based
    default.

COUNCIL_CONFIG_PATH
    Path to the council-config JSON file (active members + chairman).
    Resolved to absolute.  Overrides the ``COUNCIL_HOME``-based default.

COUNCIL_AGENT_CWD
    Neutral working directory for agent subprocesses when no repo is selected.
    Resolved to absolute.  Overrides the ``COUNCIL_HOME``-based default.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root — always the directory that *contains* the ``backend/`` package.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Data home — everything below here unless a more-specific override is set.
# ---------------------------------------------------------------------------
_COUNCIL_HOME = Path(
    os.environ.get("COUNCIL_HOME", _PROJECT_ROOT / "data")
).expanduser().resolve()


def _resolve(key: str, default: Path) -> str:
    """Return *key* from the environment resolved to an absolute path, or
    *default* as a string.

    The special SQLite name ``:memory:`` is preserved verbatim so that
    in-memory databases work; all other values are resolved via
    ``expanduser()`` followed by ``resolve()``.
    """
    if key in os.environ:
        raw = os.environ[key]
        if raw == ":memory:":
            return raw
        return str(Path(raw).expanduser().resolve())
    return str(default)


# Public path constants — strings for compatibility with every consumer
# (sqlite3, json, os.makedirs, …).
DB_PATH: str = _resolve("COUNCIL_DB_PATH", _COUNCIL_HOME / "council.db")
DATA_DIR: str = _resolve("COUNCIL_DATA_DIR", _COUNCIL_HOME / "conversations")
COUNCIL_CONFIG_PATH: str = _resolve(
    "COUNCIL_CONFIG_PATH", _COUNCIL_HOME / "council_config.json"
)
AGENT_CWD: str = _resolve("COUNCIL_AGENT_CWD", _COUNCIL_HOME / "agent-cwd")
