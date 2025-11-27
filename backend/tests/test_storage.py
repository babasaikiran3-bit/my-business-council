"""Tests for storage.py module."""

import pytest
import json
import os
from pathlib import Path
from backend import storage


class TestConversationStorage:
    """Test conversation storage operations."""

    def test_create_conversation(self, temp_data_dir, monkeypatch):
        """Test creating a new conversation."""
        monkeypatch.setattr(storage, "DATA_DIR", temp_data_dir)
        os.makedirs(temp_data_dir, exist_ok=True)

        conv_id = "test-conv-123"
        conversation = storage.create_conversation(conv_id)

        assert conversation["id"] == conv_id
        assert "created_at" in conversation
        assert conversation["messages"] == []
        assert conversation["title"] == "New Conversation"

        # Verify file was created
        file_path = Path(temp_data_dir) / f"{conv_id}.json"
        assert file_path.exists()

    def test_get_conversation(self, temp_data_dir, monkeypatch):
        """Test retrieving a conversation."""
        monkeypatch.setattr(storage, "DATA_DIR", temp_data_dir)
        os.makedirs(temp_data_dir, exist_ok=True)

        # Create a test conversation file
        conv_id = "test-conv-456"
        test_data = {
            "id": conv_id,
            "created_at": "2025-01-01T00:00:00",
            "title": "Test Conversation",
            "messages": [
                {"role": "user", "content": "Hello"}
            ]
        }
        file_path = Path(temp_data_dir) / f"{conv_id}.json"
        with open(file_path, "w") as f:
            json.dump(test_data, f)

        # Retrieve conversation
        conversation = storage.get_conversation(conv_id)

        assert conversation is not None
        assert conversation["id"] == conv_id
        assert conversation["title"] == "Test Conversation"
        assert len(conversation["messages"]) == 1

    def test_get_nonexistent_conversation(self, temp_data_dir, monkeypatch):
        """Test retrieving a conversation that doesn't exist."""
        monkeypatch.setattr(storage, "DATA_DIR", temp_data_dir)
        os.makedirs(temp_data_dir, exist_ok=True)

        conversation = storage.get_conversation("nonexistent-id")
        assert conversation is None

    def test_list_conversations(self, temp_data_dir, monkeypatch):
        """Test listing all conversations."""
        monkeypatch.setattr(storage, "DATA_DIR", temp_data_dir)
        os.makedirs(temp_data_dir, exist_ok=True)

        # Create multiple conversations
        for i in range(3):
            conv_id = f"conv-{i}"
            storage.create_conversation(conv_id)

        conversations = storage.list_conversations()

        assert len(conversations) == 3
        assert all("id" in c for c in conversations)
        assert all("created_at" in c for c in conversations)
        assert all("message_count" in c for c in conversations)

    def test_add_user_message(self, temp_data_dir, monkeypatch):
        """Test adding a user message."""
        monkeypatch.setattr(storage, "DATA_DIR", temp_data_dir)
        os.makedirs(temp_data_dir, exist_ok=True)

        conv_id = "test-conv-789"
        storage.create_conversation(conv_id)

        storage.add_user_message(conv_id, "Hello, world!")

        conversation = storage.get_conversation(conv_id)
        assert len(conversation["messages"]) == 1
        assert conversation["messages"][0]["role"] == "user"
        assert conversation["messages"][0]["content"] == "Hello, world!"

    def test_add_assistant_message(self, temp_data_dir, monkeypatch):
        """Test adding an assistant message."""
        monkeypatch.setattr(storage, "DATA_DIR", temp_data_dir)
        os.makedirs(temp_data_dir, exist_ok=True)

        conv_id = "test-conv-101"
        storage.create_conversation(conv_id)

        stage1 = [{"model": "model1", "response": "Response 1"}]
        stage2 = [{"model": "model1", "ranking": "Ranking 1"}]
        stage3 = {"model": "chairman", "response": "Final answer"}

        storage.add_assistant_message(conv_id, stage1, stage2, stage3)

        conversation = storage.get_conversation(conv_id)
        assert len(conversation["messages"]) == 1
        assert conversation["messages"][0]["role"] == "assistant"
        assert conversation["messages"][0]["stage1"] == stage1
        assert conversation["messages"][0]["stage2"] == stage2
        assert conversation["messages"][0]["stage3"] == stage3

    def test_update_conversation_title(self, temp_data_dir, monkeypatch):
        """Test updating conversation title."""
        monkeypatch.setattr(storage, "DATA_DIR", temp_data_dir)
        os.makedirs(temp_data_dir, exist_ok=True)

        conv_id = "test-conv-202"
        storage.create_conversation(conv_id)

        new_title = "Updated Title"
        storage.update_conversation_title(conv_id, new_title)

        conversation = storage.get_conversation(conv_id)
        assert conversation["title"] == new_title

    def test_list_conversations_sorted_by_date(self, temp_data_dir, monkeypatch):
        """Test that conversations are sorted by creation date (newest first)."""
        import time

        monkeypatch.setattr(storage, "DATA_DIR", temp_data_dir)
        os.makedirs(temp_data_dir, exist_ok=True)

        # Create conversations with slight delays to ensure different timestamps
        conv_ids = []
        for i in range(3):
            conv_id = f"conv-{i}"
            storage.create_conversation(conv_id)
            conv_ids.append(conv_id)
            time.sleep(0.01)

        conversations = storage.list_conversations()

        # Should be sorted newest first
        assert conversations[0]["id"] == conv_ids[-1]
        assert conversations[-1]["id"] == conv_ids[0]
