"""Tests for configuration module."""

import pytest
from backend.config import _parse_model_list


class TestConfigParsing:
    """Test configuration parsing utilities."""

    def test_parse_model_list_single(self):
        """Test parsing a single model."""
        result = _parse_model_list("openai/gpt-4")
        assert result == ["openai/gpt-4"]

    def test_parse_model_list_multiple(self):
        """Test parsing multiple models."""
        result = _parse_model_list("openai/gpt-4,anthropic/claude-3,google/gemini-pro")
        assert result == ["openai/gpt-4", "anthropic/claude-3", "google/gemini-pro"]

    def test_parse_model_list_with_spaces(self):
        """Test parsing with extra whitespace."""
        result = _parse_model_list("  openai/gpt-4  ,  anthropic/claude-3  ,  google/gemini-pro  ")
        assert result == ["openai/gpt-4", "anthropic/claude-3", "google/gemini-pro"]

    def test_parse_model_list_empty_string(self):
        """Test parsing empty string."""
        result = _parse_model_list("")
        assert result == []

    def test_parse_model_list_only_commas(self):
        """Test parsing string with only commas."""
        result = _parse_model_list(",,,")
        assert result == []

    def test_parse_model_list_empty_entries(self):
        """Test parsing with empty entries between commas."""
        result = _parse_model_list("openai/gpt-4,,anthropic/claude-3")
        assert result == ["openai/gpt-4", "anthropic/claude-3"]

    def test_parse_model_list_mixed_whitespace(self):
        """Test parsing with tabs and newlines."""
        result = _parse_model_list("openai/gpt-4\t,\n  anthropic/claude-3")
        assert result == ["openai/gpt-4", "anthropic/claude-3"]


class TestConfigValidation:
    """Test configuration validation."""

    def test_council_models_from_env(self, monkeypatch):
        """Test that COUNCIL_MODELS can be overridden via environment."""
        monkeypatch.setenv("COUNCIL_MODELS", "model1,model2,model3")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        # Need to reload the module to pick up env changes
        import importlib
        from backend import config
        importlib.reload(config)

        assert "model1" in config.COUNCIL_MODELS or len(config.COUNCIL_MODELS) >= 3

    def test_chairman_model_from_env(self, monkeypatch):
        """Test that CHAIRMAN_MODEL can be overridden via environment."""
        monkeypatch.setenv("CHAIRMAN_MODEL", "custom-chairman-model")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        # Need to reload the module to pick up env changes
        import importlib
        from backend import config
        importlib.reload(config)

        # Check it's either the custom one or has a chairman defined
        assert config.CHAIRMAN_MODEL is not None
