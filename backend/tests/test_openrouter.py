"""Tests for openrouter.py module."""

import pytest
from unittest.mock import AsyncMock, patch
from backend.openrouter import query_model, query_models_parallel


class TestQueryModel:
    """Test single model querying."""

    @pytest.mark.asyncio
    async def test_query_model_success(self, mock_openrouter_response):
        """Test successful model query."""
        # Create a mock response object
        mock_response = AsyncMock()
        mock_response.json = lambda: mock_openrouter_response
        mock_response.raise_for_status = lambda: None

        # Create a mock context manager for AsyncClient
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await query_model(
                "openai/gpt-5.1",
                [{"role": "user", "content": "Test question"}]
            )

            assert result is not None
            assert result["content"] == "This is a test response from the model."
            assert "reasoning_details" in result

    @pytest.mark.asyncio
    async def test_query_model_network_error(self):
        """Test handling of network errors."""
        with patch("httpx.AsyncClient.post") as mock_post:
            # Simulate network error
            mock_post.side_effect = Exception("Network error")

            result = await query_model(
                "openai/gpt-5.1",
                [{"role": "user", "content": "Test question"}]
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_query_model_timeout(self):
        """Test handling of timeouts."""
        import httpx

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")

            result = await query_model(
                "openai/gpt-5.1",
                [{"role": "user", "content": "Test question"}],
                timeout=1.0
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_query_model_api_error(self):
        """Test handling of API errors."""
        import httpx

        def raise_status_error():
            raise httpx.HTTPStatusError(
                "API Error", request=None, response=None
            )

        mock_response = AsyncMock()
        mock_response.raise_for_status = raise_status_error

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await query_model(
                "openai/gpt-5.1",
                [{"role": "user", "content": "Test question"}]
            )

            assert result is None


class TestQueryModelsParallel:
    """Test parallel model querying."""

    @pytest.mark.asyncio
    async def test_query_models_parallel_success(self, mock_openrouter_response):
        """Test successful parallel queries."""
        mock_response = AsyncMock()
        mock_response.json = lambda: mock_openrouter_response
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            models = ["openai/gpt-5.1", "anthropic/claude-sonnet-4.5"]
            result = await query_models_parallel(
                models,
                [{"role": "user", "content": "Test question"}]
            )

            assert len(result) == 2
            assert all(model in result for model in models)
            assert all(r is not None for r in result.values())

    @pytest.mark.asyncio
    async def test_query_models_parallel_partial_failure(self, mock_openrouter_response):
        """Test parallel queries with partial failures."""
        call_count = 0

        async def mock_post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call succeeds
                mock_response = AsyncMock()
                mock_response.json = lambda: mock_openrouter_response
                mock_response.raise_for_status = lambda: None
                return mock_response
            else:
                # Second call fails
                raise Exception("API Error")

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = mock_post_side_effect

        with patch("httpx.AsyncClient", return_value=mock_client):
            models = ["openai/gpt-5.1", "anthropic/claude-sonnet-4.5"]
            result = await query_models_parallel(
                models,
                [{"role": "user", "content": "Test question"}]
            )

            assert len(result) == 2
            # One should succeed, one should fail (None)
            successful = sum(1 for v in result.values() if v is not None)
            failed = sum(1 for v in result.values() if v is None)
            assert successful == 1
            assert failed == 1

    @pytest.mark.asyncio
    async def test_query_models_parallel_empty_list(self):
        """Test parallel queries with empty model list."""
        result = await query_models_parallel([], [{"role": "user", "content": "Test"}])
        assert result == {}
