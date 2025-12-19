"""API endpoint tests for Eternal Copilot with Supabase storage."""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Import the app
from backend.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_auth_user(test_user_id):
    """Mock the authentication to return a test user."""
    from backend.auth import AuthenticatedUser

    return AuthenticatedUser(
        id=test_user_id,
        email=f"{test_user_id}@eternal.ag",
        name="Test User",
        profile_picture_url=None
    )


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_root_endpoint(self, client):
        """Test the root health check endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "eternal-copilot" in data["service"]


class TestConversationEndpoints:
    """Tests for conversation CRUD endpoints."""

    def test_list_conversations_unauthorized(self, client):
        """Test that listing conversations requires authentication."""
        response = client.get("/api/conversations")
        assert response.status_code == 401

    def test_create_conversation_unauthorized(self, client):
        """Test that creating conversations requires authentication."""
        response = client.post("/api/conversations")
        assert response.status_code == 401

    def test_get_conversation_unauthorized(self, client):
        """Test that getting a conversation requires authentication."""
        response = client.get("/api/conversations/some-id")
        assert response.status_code == 401

    def test_list_conversations_with_auth(self, client, mock_auth_user):
        """Test listing conversations with authentication returns paginated response."""
        from backend.auth import get_current_user

        app.dependency_overrides[get_current_user] = lambda: mock_auth_user

        try:
            response = client.get("/api/conversations")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            assert "conversations" in data
            assert "has_more" in data
            assert isinstance(data["conversations"], list)
            assert isinstance(data["has_more"], bool)
        finally:
            app.dependency_overrides.clear()

    def test_create_conversation_with_auth(self, client, mock_auth_user):
        """Test creating a conversation with authentication."""
        from backend.auth import get_current_user

        app.dependency_overrides[get_current_user] = lambda: mock_auth_user

        try:
            response = client.post("/api/conversations")
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert "title" in data
            assert data["title"] == "New Conversation"
            assert "messages" in data
            assert data["messages"] == []
        finally:
            app.dependency_overrides.clear()

    def test_get_created_conversation(self, client, mock_auth_user):
        """Test getting a conversation that was just created."""
        from backend.auth import get_current_user

        app.dependency_overrides[get_current_user] = lambda: mock_auth_user

        try:
            # Create a conversation
            create_response = client.post("/api/conversations")
            assert create_response.status_code == 200
            conversation_id = create_response.json()["id"]

            # Get the conversation
            get_response = client.get(f"/api/conversations/{conversation_id}")
            assert get_response.status_code == 200
            data = get_response.json()
            assert data["id"] == conversation_id
        finally:
            app.dependency_overrides.clear()

    def test_get_nonexistent_conversation(self, client, mock_auth_user):
        """Test getting a conversation that doesn't exist."""
        from backend.auth import get_current_user
        import uuid

        app.dependency_overrides[get_current_user] = lambda: mock_auth_user

        try:
            # Use a valid UUID format that doesn't exist
            nonexistent_uuid = str(uuid.uuid4())
            response = client.get(f"/api/conversations/{nonexistent_uuid}")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestImprovePromptEndpoint:
    """Tests for improve prompt endpoint."""

    def test_improve_prompt_unauthorized(self, client):
        """Test that improve prompt requires authentication."""
        response = client.post("/api/improve-prompt", json={"content": "test"})
        assert response.status_code == 401

