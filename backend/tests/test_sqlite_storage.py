"""Tests for SQLite storage backend."""

import pytest
import tempfile
import os
from backend.storage.sqlite_storage import SQLiteStorageBackend


@pytest.fixture
def sqlite_backend():
    """Create a temporary SQLite backend for testing."""
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    backend = SQLiteStorageBackend(db_path)
    yield backend

    # Clean up
    if os.path.exists(db_path):
        os.remove(db_path)


class TestSQLiteStorage:
    """Test SQLite storage implementation."""

    def test_create_and_get_conversation(self, sqlite_backend):
        """Test creating and retrieving a conversation."""
        conv = sqlite_backend.create_conversation("test-123")

        assert conv["id"] == "test-123"
        assert conv["title"] == "New Conversation"
        assert conv["messages"] == []

        # Retrieve it
        retrieved = sqlite_backend.get_conversation("test-123")
        assert retrieved["id"] == "test-123"

    def test_list_conversations(self, sqlite_backend):
        """Test listing conversations."""
        sqlite_backend.create_conversation("conv-1")
        sqlite_backend.create_conversation("conv-2")
        sqlite_backend.create_conversation("conv-3")

        conversations = sqlite_backend.list_conversations()

        assert len(conversations) == 3
        # Should be sorted by created_at desc (newest first)
        assert conversations[0]["id"] == "conv-3"

    def test_add_user_message(self, sqlite_backend):
        """Test adding a user message."""
        sqlite_backend.create_conversation("conv-1")
        sqlite_backend.add_user_message("conv-1", "Hello, world!")

        conv = sqlite_backend.get_conversation("conv-1")
        assert len(conv["messages"]) == 1
        assert conv["messages"][0]["role"] == "user"
        assert conv["messages"][0]["content"] == "Hello, world!"

    def test_add_assistant_message(self, sqlite_backend):
        """Test adding an assistant message with costs."""
        sqlite_backend.create_conversation("conv-1")

        stage1 = [
            {"model": "model1", "response": "Response 1", "cost_usd": 0.001},
            {"model": "model2", "response": "Response 2", "cost_usd": 0.002}
        ]
        stage2 = [
            {"model": "model1", "ranking": "Ranking 1", "cost_usd": 0.003}
        ]
        stage3 = {"model": "chairman", "response": "Final", "cost_usd": 0.004}

        sqlite_backend.add_assistant_message("conv-1", stage1, stage2, stage3)

        conv = sqlite_backend.get_conversation("conv-1")
        assert len(conv["messages"]) == 1
        assert conv["messages"][0]["role"] == "assistant"
        assert conv["messages"][0]["stage1"] == stage1
        assert conv["messages"][0]["stage2"] == stage2
        assert conv["messages"][0]["stage3"] == stage3

    def test_update_title(self, sqlite_backend):
        """Test updating conversation title."""
        sqlite_backend.create_conversation("conv-1")
        sqlite_backend.update_conversation_title("conv-1", "Updated Title")

        conv = sqlite_backend.get_conversation("conv-1")
        assert conv["title"] == "Updated Title"

    def test_delete_conversation(self, sqlite_backend):
        """Test deleting a conversation."""
        sqlite_backend.create_conversation("conv-1")
        assert sqlite_backend.delete_conversation("conv-1") is True

        # Verify it's gone
        assert sqlite_backend.get_conversation("conv-1") is None

        # Try deleting non-existent
        assert sqlite_backend.delete_conversation("nonexistent") is False

    def test_search_conversations(self, sqlite_backend):
        """Test full-text search."""
        # Create conversations with searchable content
        sqlite_backend.create_conversation("conv-1")
        sqlite_backend.update_conversation_title("conv-1", "Python Programming")
        sqlite_backend.add_user_message("conv-1", "How do I use decorators in Python?")

        sqlite_backend.create_conversation("conv-2")
        sqlite_backend.update_conversation_title("conv-2", "JavaScript Basics")
        sqlite_backend.add_user_message("conv-2", "What are async functions?")

        sqlite_backend.create_conversation("conv-3")
        sqlite_backend.add_user_message("conv-3", "Python list comprehensions explained")

        # Search for "Python"
        results = sqlite_backend.search_conversations("Python")
        assert len(results) >= 1
        # Should find conversations with "Python" in title or content

        # Search for "JavaScript"
        results = sqlite_backend.search_conversations("JavaScript")
        assert len(results) >= 1

    def test_get_conversation_costs(self, sqlite_backend):
        """Test getting conversation costs."""
        sqlite_backend.create_conversation("conv-1")

        stage1 = [
            {"model": "model1", "response": "R1", "cost_usd": 0.001},
            {"model": "model2", "response": "R2", "cost_usd": 0.002}
        ]
        stage2 = [{"model": "model1", "ranking": "Rank", "cost_usd": 0.003}]
        stage3 = {"model": "chairman", "response": "Final", "cost_usd": 0.004}

        sqlite_backend.add_assistant_message("conv-1", stage1, stage2, stage3)

        costs = sqlite_backend.get_conversation_costs("conv-1")
        assert costs["stage1_usd"] == 0.003
        assert costs["stage2_usd"] == 0.003
        assert costs["stage3_usd"] == 0.004
        assert costs["total_usd"] == 0.01

    def test_get_total_costs(self, sqlite_backend):
        """Test getting total costs across conversations."""
        # Create two conversations with costs
        sqlite_backend.create_conversation("conv-1")
        stage1 = [{"model": "m1", "response": "R1", "cost_usd": 0.001}]
        stage2 = [{"model": "m1", "ranking": "Rank", "cost_usd": 0.002}]
        stage3 = {"model": "chairman", "response": "Final", "cost_usd": 0.003}
        sqlite_backend.add_assistant_message("conv-1", stage1, stage2, stage3)

        sqlite_backend.create_conversation("conv-2")
        stage1 = [{"model": "m1", "response": "R1", "cost_usd": 0.004}]
        stage2 = [{"model": "m1", "ranking": "Rank", "cost_usd": 0.005}]
        stage3 = {"model": "chairman", "response": "Final", "cost_usd": 0.006}
        sqlite_backend.add_assistant_message("conv-2", stage1, stage2, stage3)

        costs = sqlite_backend.get_total_costs()
        assert costs["conversation_count"] == 2
        assert costs["stage1_usd"] == 0.005
        assert costs["stage2_usd"] == 0.007
        assert costs["stage3_usd"] == 0.009
        assert costs["total_usd"] == 0.021

    def test_nonexistent_conversation_error(self, sqlite_backend):
        """Test that operations on nonexistent conversations raise errors."""
        with pytest.raises(ValueError):
            sqlite_backend.add_user_message("nonexistent", "Hello")

        with pytest.raises(ValueError):
            sqlite_backend.add_assistant_message("nonexistent", [], [], {})

        with pytest.raises(ValueError):
            sqlite_backend.update_conversation_title("nonexistent", "Title")
