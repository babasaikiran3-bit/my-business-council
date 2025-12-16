"""Pytest configuration and shared fixtures for Eternal Copilot tests."""

import os
import sys
import uuid
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


@pytest.fixture
def test_user_id():
    """Generate a unique test user ID for isolation."""
    return f"test_user_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_conversation_id():
    """Generate a unique conversation ID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_stage1_responses():
    """Sample Stage 1 responses for testing."""
    return [
        {
            "model": "openai/gpt-4",
            "response": "This is a test response from GPT-4."
        },
        {
            "model": "anthropic/claude-3",
            "response": "This is a test response from Claude."
        }
    ]


@pytest.fixture
def sample_stage2_evaluations():
    """Sample Stage 2 evaluations for testing."""
    return [
        {
            "model": "openai/gpt-4",
            "evaluation": "Response A is better because...",
            "parsed_ranking": ["Response A", "Response B"]
        },
        {
            "model": "anthropic/claude-3",
            "evaluation": "Response B is better because...",
            "parsed_ranking": ["Response B", "Response A"]
        }
    ]


@pytest.fixture
def sample_stage3_synthesis():
    """Sample Stage 3 synthesis for testing."""
    return {
        "model": "google/gemini-pro",
        "response": "Based on the analysis, here is the final synthesized answer..."
    }


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing."""
    return {
        "label_to_model": {
            "Response A": "openai/gpt-4",
            "Response B": "anthropic/claude-3"
        },
        "aggregate_rankings": [
            {"model": "openai/gpt-4", "avg_rank": 1.5, "votes": 2},
            {"model": "anthropic/claude-3", "avg_rank": 1.5, "votes": 2}
        ]
    }


@pytest.fixture(autouse=True)
def cleanup_test_data(test_user_id):
    """Cleanup test data after each test to prevent database pollution."""
    yield
    # Delete test conversations created by this test
    # CASCADE will delete associated messages and assistant_responses
    from backend.storage import get_supabase_client
    try:
        supabase = get_supabase_client()
        supabase.table("conversations").delete().eq("user_id", test_user_id).execute()
    except Exception as e:
        # Log but don't fail test if cleanup fails
        print(f"Warning: Failed to cleanup test data for {test_user_id}: {e}")
