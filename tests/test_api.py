"""Tests for main.py FastAPI endpoints — validation, error codes, routing."""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a TestClient with mocked config."""
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
        from backend.main import app
        with TestClient(app) as c:
            yield c


@pytest.fixture
def tmp_storage(tmp_path):
    """Use a temporary directory for storage."""
    data_dir = str(tmp_path / "conversations")
    with patch("backend.storage.DATA_DIR", data_dir):
        yield data_dir


class TestHealthCheck:
    def test_root_returns_ok(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestCreateConversation:
    def test_creates_conversation(self, client, tmp_storage):
        response = client.post("/api/conversations", json={})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "New Conversation"
        assert data["messages"] == []


class TestGetConversation:
    def test_invalid_uuid_returns_400(self, client, tmp_storage):
        response = client.get("/api/conversations/not-a-uuid")
        assert response.status_code == 400
        assert "Invalid conversation ID" in response.json()["detail"]

    def test_path_traversal_returns_400(self, client, tmp_storage):
        response = client.get("/api/conversations/../../etc/passwd")
        # FastAPI might return 400 or 404 depending on routing, but should never succeed
        assert response.status_code in (400, 404, 422)

    def test_nonexistent_uuid_returns_404(self, client, tmp_storage):
        response = client.get("/api/conversations/550e8400-e29b-41d4-a716-446655440099")
        assert response.status_code == 404

    def test_existing_conversation_returns_200(self, client, tmp_storage):
        # Create a conversation first
        create_resp = client.post("/api/conversations", json={})
        conv_id = create_resp.json()["id"]

        response = client.get(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        assert response.json()["id"] == conv_id


class TestListConversations:
    def test_empty_list(self, client, tmp_storage):
        response = client.get("/api/conversations")
        assert response.status_code == 200
        assert response.json() == []

    def test_lists_created_conversations(self, client, tmp_storage):
        client.post("/api/conversations", json={})
        client.post("/api/conversations", json={})

        response = client.get("/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        for conv in data:
            assert "id" in conv
            assert "title" in conv
            assert "message_count" in conv


class TestSendMessageValidation:
    def test_empty_content_rejected(self, client, tmp_storage):
        """Empty string should be rejected by min_length=1 validation."""
        create_resp = client.post("/api/conversations", json={})
        conv_id = create_resp.json()["id"]

        response = client.post(
            f"/api/conversations/{conv_id}/message",
            json={"content": ""}
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_missing_content_rejected(self, client, tmp_storage):
        """Missing content field should be rejected."""
        create_resp = client.post("/api/conversations", json={})
        conv_id = create_resp.json()["id"]

        response = client.post(
            f"/api/conversations/{conv_id}/message",
            json={}
        )
        assert response.status_code == 422

    def test_invalid_conversation_id_returns_400(self, client, tmp_storage):
        response = client.post(
            "/api/conversations/not-a-uuid/message",
            json={"content": "Hello"}
        )
        assert response.status_code == 400

    def test_nonexistent_conversation_returns_404(self, client, tmp_storage):
        response = client.post(
            "/api/conversations/550e8400-e29b-41d4-a716-446655440099/message",
            json={"content": "Hello"}
        )
        assert response.status_code == 404


class TestSendMessageStreamValidation:
    def test_empty_content_rejected(self, client, tmp_storage):
        create_resp = client.post("/api/conversations", json={})
        conv_id = create_resp.json()["id"]

        response = client.post(
            f"/api/conversations/{conv_id}/message/stream",
            json={"content": ""}
        )
        assert response.status_code == 422

    def test_invalid_conversation_id_returns_400(self, client, tmp_storage):
        response = client.post(
            "/api/conversations/not-a-uuid/message/stream",
            json={"content": "Hello"}
        )
        assert response.status_code == 400

    def test_nonexistent_conversation_returns_404(self, client, tmp_storage):
        response = client.post(
            "/api/conversations/550e8400-e29b-41d4-a716-446655440099/message/stream",
            json={"content": "Hello"}
        )
        assert response.status_code == 404
