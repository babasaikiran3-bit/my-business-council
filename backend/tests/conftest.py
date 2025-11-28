"""Pytest configuration and fixtures."""

import pytest
import os
import tempfile
import shutil
from pathlib import Path

# Set required environment variables before importing backend modules
os.environ.setdefault("OPENROUTER_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("LOG_LEVEL", "DEBUG")


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_openrouter_response():
    """Mock OpenRouter API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "This is a test response from the model.",
                    "role": "assistant"
                }
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-api-key-123")
    monkeypatch.setenv("DATA_DIR", "test_data")


@pytest.fixture
def sample_stage1_results():
    """Sample Stage 1 results for testing."""
    return [
        {
            "model": "openai/gpt-5.1",
            "response": "This is the first response with detailed analysis."
        },
        {
            "model": "anthropic/claude-sonnet-4.5",
            "response": "This is the second response with different insights."
        },
        {
            "model": "google/gemini-3-pro-preview",
            "response": "This is the third response from a different perspective."
        }
    ]


@pytest.fixture
def sample_ranking_text():
    """Sample ranking text for testing parsing."""
    return """Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B"""
