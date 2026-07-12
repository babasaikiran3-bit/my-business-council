"""Ordered, transactional schema migrations with version tracking.

Every schema change past the initial bootstrap is recorded in the ``_migrations``
table so Room (and future features) start from a known version instead of relying
on ad-hoc ``ALTER TABLE`` calls during normal requests.

Usage::

    from .migrations import migrate, current_version

    conn = sqlite3.connect(...)
    applied = migrate(conn)
    print(f"Now at version {current_version(conn)}; applied {applied} migration(s)")
"""

from __future__ import annotations

import sqlite3
from typing import Callable, List, Tuple

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_MigrationFn = Callable[[sqlite3.Connection], None]

_migrations: List[Tuple[int, str, _MigrationFn]] = []


def register(version: int, name: str):
    """Decorator that registers a migration function at *version*."""

    def deco(fn: _MigrationFn) -> _MigrationFn:
        _migrations.append((version, name, fn))
        return fn

    return deco


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    """Create the bookkeeping table if it does not exist (idempotent)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
            version     INTEGER PRIMARY KEY,
            name        TEXT    NOT NULL,
            applied_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def current_version(conn: sqlite3.Connection) -> int:
    """Highest applied migration version, or 0 if none."""
    _ensure_migrations_table(conn)
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) FROM _migrations"
    ).fetchone()
    return row[0]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def migrate(conn: sqlite3.Connection) -> int:
    """Apply every pending migration in version order, each in its own transaction.

    Returns the number of migrations applied (0 when already up-to-date).
    """
    _ensure_migrations_table(conn)
    version = current_version(conn)

    pending = sorted(
        [(v, n, fn) for v, n, fn in _migrations if v > version],
        key=lambda x: x[0],
    )

    applied = 0
    for ver, name, fn in pending:
        conn.execute("BEGIN")
        try:
            fn(conn)
            conn.execute(
                "INSERT INTO _migrations (version, name) VALUES (?, ?)",
                (ver, name),
            )
            conn.execute("COMMIT")
            applied += 1
        except Exception:
            conn.execute("ROLLBACK")
            raise

    return applied


# ====================================================================
# Migration definitions
# ====================================================================


@register(1, "bootstrap_schema")
def _m001_bootstrap(conn: sqlite3.Connection) -> None:
    """Initial schema: conversations + messages tables (idempotent).

    Uses individual ``execute`` calls so all DDL participates in the
    caller's explicit transaction.  ``executescript`` would issue an
    implicit ``COMMIT`` first, breaking atomicity with the version
    insertion that follows.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id         TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            title      TEXT NOT NULL DEFAULT 'New Conversation',
            repo_path  TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            position        INTEGER NOT NULL,
            role            TEXT NOT NULL,
            data            TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_messages_conv
            ON messages(conversation_id, position)
        """
    )


@register(2, "add_repo_path_column")
def _m002_add_repo_path(conn: sqlite3.Connection) -> None:
    """Add ``repo_path`` to conversations for DBs created before the column existed."""
    cols = [
        r[1]
        for r in conn.execute("PRAGMA table_info(conversations)").fetchall()
    ]
    if "repo_path" not in cols:
        conn.execute("ALTER TABLE conversations ADD COLUMN repo_path TEXT")


@register(3, "add_message_position_unique")
def _m003_message_position_unique(conn: sqlite3.Connection) -> None:
    """Unique constraint on (conversation_id, position) to prevent duplicates."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_messages_conv_pos'"
    ).fetchone()
    if row is None:
        conn.execute(
            "CREATE UNIQUE INDEX idx_messages_conv_pos "
            "ON messages(conversation_id, position)"
        )
