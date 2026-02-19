"""Tests for openrouter.py — error handling, response parsing, parallel queries."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock


# We need to set the env var before importing the module
@pytest.fixture(autouse=True)
def mock_config():
    with patch("backend.openrouter.OPENROUTER_API_KEY", "test-key"), \
         patch("backend.openrouter.OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"):
        yield


from backend.openrouter import query_model, query_models_parallel


class TestQueryModel:
    """Tests for individual model queries and error handling."""

    @pytest.mark.asyncio
    async def test_successful_query(self):
        """Should return content from a successful API response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello world", "reasoning_details": None}}]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await query_model("test/model", [{"role": "user", "content": "hi"}])

        assert result is not None
        assert result["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        """Should return None on timeout."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await query_model("test/model", [{"role": "user", "content": "hi"}], timeout=1.0)

        assert result is None

    @pytest.mark.asyncio
    async def test_401_returns_none(self):
        """Should return None on authentication failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await query_model("test/model", [{"role": "user", "content": "hi"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_429_rate_limit_returns_none(self):
        """Should return None on rate limit."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await query_model("test/model", [{"role": "user", "content": "hi"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_500_server_error_returns_none(self):
        """Should return None on server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await query_model("test/model", [{"role": "user", "content": "hi"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_json_missing_choices_returns_none(self):
        """Should return None when response JSON is missing 'choices' key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"error": "something went wrong"}  # No 'choices'

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await query_model("test/model", [{"role": "user", "content": "hi"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_json_empty_choices_returns_none(self):
        """Should return None when choices array is empty."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"choices": []}  # Empty choices

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await query_model("test/model", [{"role": "user", "content": "hi"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_reasoning_details_extracted(self):
        """Should extract reasoning_details when present."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Answer",
                    "reasoning_details": "Thinking step by step..."
                }
            }]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await query_model("test/model", [{"role": "user", "content": "hi"}])

        assert result["content"] == "Answer"
        assert result["reasoning_details"] == "Thinking step by step..."

    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_none(self):
        """Should return None on unexpected exceptions (e.g. DNS failure)."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = OSError("DNS resolution failed")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await query_model("test/model", [{"role": "user", "content": "hi"}])

        assert result is None


class TestQueryModelsParallel:
    """Tests for parallel model queries."""

    @pytest.mark.asyncio
    async def test_maps_models_to_responses(self):
        """Should return dict mapping each model to its response."""
        async def mock_query(model, messages, timeout=120.0):
            return {"content": f"Response from {model}"}

        with patch("backend.openrouter.query_model", side_effect=mock_query):
            result = await query_models_parallel(
                ["model-a", "model-b"],
                [{"role": "user", "content": "hi"}]
            )

        assert result["model-a"]["content"] == "Response from model-a"
        assert result["model-b"]["content"] == "Response from model-b"

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """Some models fail, others succeed — should return None for failures."""
        async def mock_query(model, messages, timeout=120.0):
            if model == "model-b":
                return None  # Simulates failure
            return {"content": f"Response from {model}"}

        with patch("backend.openrouter.query_model", side_effect=mock_query):
            result = await query_models_parallel(
                ["model-a", "model-b", "model-c"],
                [{"role": "user", "content": "hi"}]
            )

        assert result["model-a"] is not None
        assert result["model-b"] is None
        assert result["model-c"] is not None

    @pytest.mark.asyncio
    async def test_all_fail(self):
        """All models fail — should return dict of Nones."""
        async def mock_query(model, messages, timeout=120.0):
            return None

        with patch("backend.openrouter.query_model", side_effect=mock_query):
            result = await query_models_parallel(
                ["model-a", "model-b"],
                [{"role": "user", "content": "hi"}]
            )

        assert result["model-a"] is None
        assert result["model-b"] is None

    @pytest.mark.asyncio
    async def test_empty_model_list(self):
        """Empty model list should return empty dict."""
        result = await query_models_parallel([], [{"role": "user", "content": "hi"}])
        assert result == {}
