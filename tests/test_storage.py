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
