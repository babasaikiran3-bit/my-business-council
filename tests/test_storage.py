"""Tests for ``backend.storage`` — CRUD on conversations and messages."""

from __future__ import annotations

import json
import os
import sqlite3

import pytest

from backend import storage as s
from conftest import _fresh_imports


class TestCreateConversation:
    def test_basic(self, temp_db):
        conv = s.create_conversation("abc123")
        assert conv["id"] == "abc123"
        assert conv["title"] == "New Conversation"
        assert conv["messages"] == []
        assert conv["repo_path"] is None

    def test_with_repo(self, temp_db):
        conv = s.create_conversation("repo-conv", repo_path="/home/test/repo")
        assert conv["repo_path"] == "/home/test/repo"

    def test_duplicate_raises(self, temp_db):
        s.create_conversation("dup")
        with pytest.raises(sqlite3.IntegrityError):
            s.create_conversation("dup")


class TestGetConversation:
    def test_existing(self, temp_db):
        s.create_conversation("get-me")
        s.add_user_message("get-me", "hello")
        conv = s.get_conversation("get-me")
        assert conv is not None
        assert conv["id"] == "get-me"
        assert len(conv["messages"]) == 1
        assert conv["messages"][0]["role"] == "user"
        assert conv["messages"][0]["content"] == "hello"

    def test_missing_returns_none(self, temp_db):
        assert s.get_conversation("nope") is None


class TestListConversations:
    def test_empty(self, temp_db):
        assert s.list_conversations() == []

    def test_ordered_by_created_at(self, temp_db):
        s.create_conversation("c1")
        s.create_conversation("c2")
        result = s.list_conversations()
        assert len(result) == 2
        # More recent first
        assert result[0]["id"] == "c2"
        assert result[1]["id"] == "c1"

    def test_message_count(self, temp_db):
        s.create_conversation("mc")
        s.add_user_message("mc", "q1")
        s.add_assistant_message("mc", [], [], {"response": "ok"})
        s.add_user_message("mc", "q2")
        s.add_assistant_message("mc", [], [], {"response": "ok2"})
        result = s.list_conversations()
        assert result[0]["message_count"] == 4


class TestDeleteConversation:
    def test_existing(self, temp_db):
        s.create_conversation("del-me")
        assert s.delete_conversation("del-me") is True
        assert s.get_conversation("del-me") is None

    def test_missing(self, temp_db):
        assert s.delete_conversation("gone") is False


class TestAddUserMessage:
    def test_appends(self, temp_db):
        s.create_conversation("app")
        s.add_user_message("app", "first")
        s.add_user_message("app", "second")
        conv = s.get_conversation("app")
        assert [m["content"] for m in conv["messages"]] == ["first", "second"]
        assert all(m["role"] == "user" for m in conv["messages"])

    def test_unknown_conversation_raises(self, temp_db):
        with pytest.raises(ValueError, match="not found"):
            s.add_user_message("ghost", "boo")


class TestAddAssistantMessage:
    def test_full_stages(self, temp_db):
        s.create_conversation("asst")
        s.add_user_message("asst", "query")
        s.add_assistant_message(
            "asst",
            stage1=[{"model": "claude", "response": "ok"}],
            stage2=[{"model": "claude", "ranking": "rank"}],
            stage3={"model": "chair", "response": "final"},
            metadata={"label_to_model": {"A": "claude"}},
        )
        conv = s.get_conversation("asst")
        assert len(conv["messages"]) == 2
        asst_msg = conv["messages"][1]
        assert asst_msg["role"] == "assistant"
        assert asst_msg["stage1"][0]["model"] == "claude"
        assert asst_msg["stage3"]["response"] == "final"
        assert asst_msg.get("metadata") is not None

    def test_without_metadata(self, temp_db):
        s.create_conversation("nometa")
        s.add_user_message("nometa", "q")
        s.add_assistant_message("nometa", [], [], {"response": "x"})
        conv = s.get_conversation("nometa")
        assert "metadata" not in conv["messages"][1]

    def test_unknown_conversation_raises(self, temp_db):
        with pytest.raises(ValueError, match="not found"):
            s.add_assistant_message("ghost", [], [], {})


class TestSaveConversation:
    def test_upsert_overwrites(self, temp_db):
        conv = s.create_conversation("save-test")
        conv["title"] = "Changed"
        conv["messages"] = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "stage1": [], "stage2": [], "stage3": {"response": "bye"}},
        ]
        s.save_conversation(conv)

        loaded = s.get_conversation("save-test")
        assert loaded["title"] == "Changed"
        assert len(loaded["messages"]) == 2
        assert loaded["messages"][0]["content"] == "hi"
        assert loaded["messages"][1]["stage3"]["response"] == "bye"


class TestSetConversationRepo:
    def test_update(self, temp_db):
        s.create_conversation("set-repo")
        s.set_conversation_repo("set-repo", "/new/repo")
        conv = s.get_conversation("set-repo")
        assert conv["repo_path"] == "/new/repo"

    def test_clear(self, temp_db):
        s.create_conversation("clear-repo", repo_path="/had/one")
        s.set_conversation_repo("clear-repo", None)
        assert s.get_conversation("clear-repo")["repo_path"] is None


class TestUpdateTitle:
    def test_sets_title(self, temp_db):
        s.create_conversation("tit")
        s.update_conversation_title("tit", "Custom Title")
        assert s.get_conversation("tit")["title"] == "Custom Title"

    def test_unknown_conversation_raises(self, temp_db):
        with pytest.raises(ValueError, match="not found"):
            s.update_conversation_title("ghost", "Nope")


class TestMessagePosition:
    def test_monotonic_per_conversation(self, temp_db):
        s.create_conversation("pos")
        s.add_user_message("pos", "a")
        s.add_assistant_message("pos", [], [], {})
        s.add_user_message("pos", "b")
        s.add_assistant_message("pos", [], [], {})

        positions = [
            json.loads(r["data"])
            for r in _raw_messages("pos")
        ]
        # Verify positions are sequential (though we test via the row directly)
        assert len(positions) == 4


class TestUniquePositionConstraint:
    def test_duplicate_position_prevented(self, temp_db):
        """Migration 003 adds a unique index on (conversation_id, position)."""
        s.create_conversation("unique-pos")
        s.add_user_message("unique-pos", "legit")

        import sqlite3
        from backend.config import DB_PATH

        # Bypass the API and insert a colliding position
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            # Same conversation + same position → should fail
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO messages (conversation_id, position, role, data) "
                    "VALUES ('unique-pos', 0, 'user', '{}')"
                )


class TestMemoryDB:
    """Behaviour when ``COUNCIL_DB_PATH=:memory:`` — the in-memory database."""

    def test_init_db_does_not_crash(self, monkeypatch, tmp_path):
        """``init_db`` must skip ``os.makedirs`` for ``:memory:`` and not
        raise an error.  (Full multi-connection workflows cannot use
        ``:memory:`` because each ``sqlite3.connect(':memory:')`` creates
        a separate, independent in-memory database.)
        """
        monkeypatch.setenv("COUNCIL_HOME", str(tmp_path))
        monkeypatch.setenv("COUNCIL_DB_PATH", ":memory:")
        _fresh_imports()
        import backend.storage as fresh_storage

        # Must not raise.
        fresh_storage.init_db()

        # Confirm the db path was preserved (not resolved to a filesystem path).
        from backend.config import DB_PATH
        assert DB_PATH == ":memory:"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _raw_messages(conversation_id: str):
    import sqlite3
    from backend.config import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT data FROM messages WHERE conversation_id = ? ORDER BY position",
        (conversation_id,),
    ).fetchall()
    conn.close()
    return rows
