"""Tests for storage.py — UUID validation, atomic writes, file locking."""

import json
import os
import pytest
import tempfile
from unittest.mock import patch

from backend.storage import (
    _validate_conversation_id,
    get_conversation_path,
    create_conversation,
    get_conversation,
    save_conversation,
    list_conversations,
)


class TestValidateConversationId:
    """Tests for UUID validation (path traversal prevention)."""

    def test_valid_uuid(self):
        result = _validate_conversation_id("550e8400-e29b-41d4-a716-446655440000")
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError, match="Invalid conversation ID"):
            _validate_conversation_id("../../etc/passwd")

    def test_dot_dot_rejected(self):
        with pytest.raises(ValueError, match="Invalid conversation ID"):
            _validate_conversation_id("../secrets")

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="Invalid conversation ID"):
            _validate_conversation_id("")

    def test_arbitrary_string_rejected(self):
        with pytest.raises(ValueError, match="Invalid conversation ID"):
            _validate_conversation_id("not-a-uuid")

    def test_none_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            _validate_conversation_id(None)

    def test_slash_in_id_rejected(self):
        with pytest.raises(ValueError, match="Invalid conversation ID"):
            _validate_conversation_id("foo/bar")


class TestStorageOperations:
    """Tests for create, read, save, list operations."""

    @pytest.fixture
    def tmp_data_dir(self, tmp_path):
        """Use a temporary directory for storage tests."""
        data_dir = str(tmp_path / "conversations")
        with patch("backend.storage.DATA_DIR", data_dir):
            yield data_dir

    def test_create_and_get_conversation(self, tmp_data_dir):
        conv_id = "550e8400-e29b-41d4-a716-446655440000"
        conv = create_conversation(conv_id)

        assert conv["id"] == conv_id
        assert conv["title"] == "New Conversation"
        assert conv["messages"] == []

        # Retrieve it
        loaded = get_conversation(conv_id)
        assert loaded["id"] == conv_id

    def test_get_nonexistent_conversation(self, tmp_data_dir):
        result = get_conversation("550e8400-e29b-41d4-a716-446655440001")
        assert result is None

    def test_save_conversation_atomic(self, tmp_data_dir):
        conv_id = "550e8400-e29b-41d4-a716-446655440000"
        create_conversation(conv_id)

        conv = get_conversation(conv_id)
        conv["messages"].append({"role": "user", "content": "Hello"})
        save_conversation(conv)

        loaded = get_conversation(conv_id)
        assert len(loaded["messages"]) == 1
        assert loaded["messages"][0]["content"] == "Hello"

    def test_list_conversations(self, tmp_data_dir):
        create_conversation("550e8400-e29b-41d4-a716-446655440000")
        create_conversation("550e8400-e29b-41d4-a716-446655440001")

        convs = list_conversations()
        assert len(convs) == 2
        # Should have metadata fields
        for conv in convs:
            assert "id" in conv
            assert "created_at" in conv
            assert "title" in conv
            assert "message_count" in conv

    def test_no_temp_files_left_after_save(self, tmp_data_dir):
        conv_id = "550e8400-e29b-41d4-a716-446655440000"
        create_conversation(conv_id)

        conv = get_conversation(conv_id)
        save_conversation(conv)

        # Check no .tmp files remain
        files = os.listdir(tmp_data_dir)
        tmp_files = [f for f in files if f.endswith('.tmp')]
        assert tmp_files == []

    def test_invalid_id_in_get_raises(self, tmp_data_dir):
        with pytest.raises(ValueError):
            get_conversation("../../../etc/passwd")

    def test_add_user_message(self, tmp_data_dir):
        from backend.storage import add_user_message
        conv_id = "550e8400-e29b-41d4-a716-446655440000"
        create_conversation(conv_id)

        add_user_message(conv_id, "Hello!")

        conv = get_conversation(conv_id)
        assert len(conv["messages"]) == 1
        assert conv["messages"][0]["role"] == "user"
        assert conv["messages"][0]["content"] == "Hello!"

    def test_add_assistant_message(self, tmp_data_dir):
        from backend.storage import add_assistant_message
        conv_id = "550e8400-e29b-41d4-a716-446655440000"
        create_conversation(conv_id)

        stage1 = [{"model": "m1", "response": "answer"}]
        stage2 = [{"model": "m1", "ranking": "...", "parsed_ranking": []}]
        stage3 = {"model": "chairman", "response": "synthesis"}
        add_assistant_message(conv_id, stage1, stage2, stage3)

        conv = get_conversation(conv_id)
        assert len(conv["messages"]) == 1
        msg = conv["messages"][0]
        assert msg["role"] == "assistant"
        assert msg["stage1"] == stage1
        assert msg["stage2"] == stage2
        assert msg["stage3"] == stage3

    def test_update_conversation_title(self, tmp_data_dir):
        from backend.storage import update_conversation_title
        conv_id = "550e8400-e29b-41d4-a716-446655440000"
        create_conversation(conv_id)

        update_conversation_title(conv_id, "New Title")

        conv = get_conversation(conv_id)
        assert conv["title"] == "New Title"

    def test_add_message_to_nonexistent_raises(self, tmp_data_dir):
        from backend.storage import add_user_message
        with pytest.raises(ValueError, match="not found"):
            add_user_message("550e8400-e29b-41d4-a716-446655440099", "Hello")

    def test_update_title_nonexistent_raises(self, tmp_data_dir):
        from backend.storage import update_conversation_title
        with pytest.raises(ValueError, match="not found"):
            update_conversation_title("550e8400-e29b-41d4-a716-446655440099", "Title")

    def test_multiple_messages_accumulate(self, tmp_data_dir):
        from backend.storage import add_user_message, add_assistant_message
        conv_id = "550e8400-e29b-41d4-a716-446655440000"
        create_conversation(conv_id)

        add_user_message(conv_id, "First question")
        add_assistant_message(conv_id, [], [], {"model": "m", "response": "r"})
        add_user_message(conv_id, "Second question")

        conv = get_conversation(conv_id)
        assert len(conv["messages"]) == 3
        assert conv["messages"][0]["role"] == "user"
        assert conv["messages"][1]["role"] == "assistant"
        assert conv["messages"][2]["role"] == "user"

    def test_list_conversations_returns_correct_message_count(self, tmp_data_dir):
        from backend.storage import add_user_message
        conv_id = "550e8400-e29b-41d4-a716-446655440000"
        create_conversation(conv_id)
        add_user_message(conv_id, "Hello")
        add_user_message(conv_id, "World")

        convs = list_conversations()
        assert convs[0]["message_count"] == 2

    def test_save_preserves_data_integrity(self, tmp_data_dir):
        """Data written and read back should be identical."""
        conv_id = "550e8400-e29b-41d4-a716-446655440000"
        create_conversation(conv_id)

        conv = get_conversation(conv_id)
        conv["messages"].append({
            "role": "user",
            "content": "Special chars: <>&'\"\n\ttab"
        })
        save_conversation(conv)

        loaded = get_conversation(conv_id)
        assert loaded["messages"][0]["content"] == "Special chars: <>&'\"\n\ttab"
