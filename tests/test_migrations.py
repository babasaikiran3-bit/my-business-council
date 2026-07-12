"""Tests for ``backend.migrations`` — ordering, versioning, idempotency."""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest

from backend import migrations


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with the standard production settings."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class TestCurrentVersion:
    def test_zero_on_empty_db(self, temp_db_raw):
        with _connect(temp_db_raw) as conn:
            assert migrations.current_version(conn) == 0

    def test_creates_migrations_table(self, temp_db):
        with _connect(temp_db) as conn:
            _ = migrations.current_version(conn)
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations'"
            ).fetchone()
            assert row is not None


class TestMigrateFreshDb:
    def test_applies_all_migrations(self, temp_db_raw):
        with _connect(temp_db_raw) as conn:
            applied = migrations.migrate(conn)
            assert applied >= 3  # at least the three we defined
            version = migrations.current_version(conn)
            assert version >= 3

            # Verify expected tables exist
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "conversations" in tables
            assert "messages" in tables
            assert "_migrations" in tables

    def test_migration_records(self, temp_db):
        with _connect(temp_db) as conn:
            migrations.migrate(conn)
            rows = conn.execute(
                "SELECT version, name FROM _migrations ORDER BY version"
            ).fetchall()
            names = [r["name"] for r in rows]
            assert "bootstrap_schema" in names
            assert "add_repo_path_column" in names
            assert "add_message_position_unique" in names

    def test_version_order_is_monotonic(self, temp_db):
        with _connect(temp_db) as conn:
            migrations.migrate(conn)
            versions = [
                r[0]
                for r in conn.execute(
                    "SELECT version FROM _migrations ORDER BY version"
                ).fetchall()
            ]
            assert versions == sorted(versions)
            assert versions[0] >= 1


class TestIdempotency:
    def test_second_run_applies_zero(self, temp_db_raw):
        with _connect(temp_db_raw) as conn:
            first = migrations.migrate(conn)
            assert first > 0
            second = migrations.migrate(conn)
            assert second == 0

    def test_individual_migration_is_idempotent(self, temp_db):
        """Each migration function can be called repeatedly without error."""
        with _connect(temp_db) as conn:
            # Bootstrap first
            migrations.migrate(conn)

            # Call each migration function manually a second time
            from backend.migrations import _m001_bootstrap, _m002_add_repo_path, _m003_message_position_unique

            _m001_bootstrap(conn)  # IF NOT EXISTS handles this
            _m002_add_repo_path(conn)  # checks column existence
            _m003_message_position_unique(conn)  # checks index existence


class TestIntegrityPolicies:
    def test_busy_timeout_is_set(self, temp_db):
        with _connect(temp_db) as conn:
            # Run migrations so the connection gets the timeout
            migrations.migrate(conn)  # not needed, timeout is on connection open
            row = conn.execute("PRAGMA busy_timeout").fetchone()
            assert row[0] == 5000

    def test_wal_enabled(self, temp_db):
        with _connect(temp_db) as conn:
            row = conn.execute("PRAGMA journal_mode").fetchone()
            assert row[0].lower() == "wal"

    def test_foreign_keys_enabled(self, temp_db):
        with _connect(temp_db) as conn:
            row = conn.execute("PRAGMA foreign_keys").fetchone()
            assert row[0] == 1


class TestRepoPathColumn:
    def test_exists_after_migration(self, temp_db):
        with _connect(temp_db) as conn:
            migrations.migrate(conn)
            cols = [
                r[1]
                for r in conn.execute(
                    "PRAGMA table_info(conversations)"
                ).fetchall()
            ]
            assert "repo_path" in cols

    def test_migration_detects_existing_column(self, temp_db):
        """Migration 2 should be a no-op when the column already exists."""
        with _connect(temp_db) as conn:
            migrations.migrate(conn)
            # Re-run migration 2 explicitly — should not error
            from backend.migrations import _m002_add_repo_path

            _m002_add_repo_path(conn)  # no exception


class TestTransactionRollback:
    """Proof that a failing migration rolls back *both* its schema effects
    and its version record — the pair is atomic."""

    def test_failing_migration_leaves_no_trace(self, temp_db_raw):
        """A migration that creates DDL then raises must not persist either
        the schema object or its ``_migrations`` version row."""
        import backend.migrations as m

        # A migration that does schema work then deliberately fails.
        def _bad(conn):
            conn.execute("CREATE TABLE should_not_exist (x INTEGER)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_bad ON should_not_exist(x)")
            raise RuntimeError("simulated failure")

        # Inject at a high version so it runs after the real migrations.
        original = list(m._migrations)
        m._migrations.append((9999, "bad_migration", _bad))
        try:
            with _connect(temp_db_raw) as conn:
                with pytest.raises(RuntimeError, match="simulated failure"):
                    m.migrate(conn)

            # Fresh connection — only the good migrations' effects survive.
            with _connect(temp_db_raw) as conn:
                tables = {
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                assert "conversations" in tables
                assert "messages" in tables
                assert "_migrations" in tables
                assert "should_not_exist" not in tables  # <-- rolled back

                row = conn.execute(
                    "SELECT 1 FROM _migrations WHERE version = 9999"
                ).fetchone()
                assert row is None  # <-- version record also rolled back

                # Only the real migrations (1,2,3) are recorded.
                assert m.current_version(conn) == 3
        finally:
            m._migrations[:] = original

    def test_failing_migration_does_not_break_prior_migrations(
        self, temp_db_raw
    ):
        """A failure in migration N must not undo migrations < N."""
        import backend.migrations as m

        def _bad(conn):
            # This DDL executes but the raise prevents the version insert.
            conn.execute("CREATE TABLE IF NOT EXISTS innocent (y TEXT)")
            raise RuntimeError("boom")

        original = list(m._migrations)
        m._migrations.append((9999, "bad2", _bad))
        try:
            with _connect(temp_db_raw) as conn:
                with pytest.raises(RuntimeError, match="boom"):
                    m.migrate(conn)

            with _connect(temp_db_raw) as conn:
                tables = {
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                assert "conversations" in tables
                assert "_migrations" in tables
                assert "innocent" not in tables  # rolled back with its transaction
        finally:
            m._migrations[:] = original


class TestUniqueMessagePosition:
    def test_index_exists_after_migration(self, temp_db):
        with _connect(temp_db) as conn:
            migrations.migrate(conn)
            row = conn.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='index' AND name='idx_messages_conv_pos'"
            ).fetchone()
            assert row is not None

    def test_enforces_uniqueness(self, temp_db):
        import sqlite3 as _sqlite3

        with _connect(temp_db) as conn:
            migrations.migrate(conn)
            conn.execute(
                "INSERT INTO conversations (id, created_at) VALUES ('c1', ?)",
                (datetime.utcnow().isoformat(),),
            )
            conn.execute(
                "INSERT INTO messages (conversation_id, position, role, data) "
                "VALUES ('c1', 1, 'user', '{}')"
            )
            with pytest.raises(_sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO messages (conversation_id, position, role, data) "
                    "VALUES ('c1', 1, 'user', '{}')"
                )
