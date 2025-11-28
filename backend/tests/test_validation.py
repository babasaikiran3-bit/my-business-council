"""Tests for input validation and security."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from backend.main import SendMessageRequest, validate_conversation_id


class TestMessageValidation:
    """Test message content validation."""

    def test_valid_message(self):
        """Test that valid messages pass validation."""
        msg = SendMessageRequest(content="This is a valid message")
        assert msg.content == "This is a valid message"

    def test_message_strips_whitespace(self):
        """Test that messages are stripped of leading/trailing whitespace."""
        msg = SendMessageRequest(content="  \n  Valid message  \n  ")
        assert msg.content == "Valid message"

    def test_empty_message_fails(self):
        """Test that empty messages fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(content="")
        # Pydantic min_length validator triggers before our custom validator
        assert "at least 1 character" in str(exc_info.value)

    def test_whitespace_only_message_fails(self):
        """Test that whitespace-only messages fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(content="   \n\t  \n  ")
        assert "empty" in str(exc_info.value).lower()

    def test_message_too_long_fails(self):
        """Test that excessively long messages fail validation."""
        with pytest.raises(ValidationError):
            SendMessageRequest(content="a" * 10001)

    def test_line_too_long_fails(self):
        """Test that messages with excessively long lines fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(content="a" * 5001)
        assert "5000" in str(exc_info.value)

    def test_too_many_lines_fails(self):
        """Test that messages with too many lines fail validation."""
        # Create a message with actual content and too many lines (>500 newlines)
        content = "\n".join(["line"] * 502)  # 502 items = 501 newlines
        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(content=content)
        assert "500" in str(exc_info.value)

    def test_message_with_newlines(self):
        """Test that messages with reasonable newlines work."""
        content = "Line 1\nLine 2\nLine 3"
        msg = SendMessageRequest(content=content)
        assert msg.content == content

    def test_message_max_length_boundary(self):
        """Test message at exactly max length with multiple short lines."""
        # Create a message close to max length with short lines
        content = "\n".join(["line content here"] * 500)  # ~8500 chars
        msg = SendMessageRequest(content=content)
        assert len(msg.content) > 8000


class TestConversationIDValidation:
    """Test conversation ID validation."""

    def test_valid_uuid(self):
        """Test that valid UUID-like IDs pass validation."""
        valid_id = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_conversation_id(valid_id)
        assert result == valid_id

    def test_alphanumeric_id(self):
        """Test that alphanumeric IDs pass validation."""
        valid_id = "abc123-def456"
        result = validate_conversation_id(valid_id)
        assert result == valid_id

    def test_path_traversal_fails(self):
        """Test that path traversal attempts are blocked."""
        with pytest.raises(HTTPException) as exc_info:
            validate_conversation_id("../../../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_double_dot_fails(self):
        """Test that double dots are blocked."""
        with pytest.raises(HTTPException) as exc_info:
            validate_conversation_id("conv..123")
        assert exc_info.value.status_code == 400

    def test_forward_slash_fails(self):
        """Test that forward slashes are blocked."""
        with pytest.raises(HTTPException) as exc_info:
            validate_conversation_id("conv/123")
        assert exc_info.value.status_code == 400

    def test_backslash_fails(self):
        """Test that backslashes are blocked."""
        with pytest.raises(HTTPException) as exc_info:
            validate_conversation_id("conv\\123")
        assert exc_info.value.status_code == 400

    def test_special_chars_fail(self):
        """Test that special characters are blocked."""
        invalid_chars = ['@', '#', '$', '%', '&', '*', '(', ')', '=', '+', '[', ']', '{', '}']
        for char in invalid_chars:
            with pytest.raises(HTTPException):
                validate_conversation_id(f"conv{char}123")

    def test_too_long_id_fails(self):
        """Test that excessively long IDs are blocked."""
        with pytest.raises(HTTPException) as exc_info:
            validate_conversation_id("a" * 101)
        assert exc_info.value.status_code == 400

    def test_boundary_length_id(self):
        """Test ID at exactly max length."""
        valid_id = "a" * 100
        result = validate_conversation_id(valid_id)
        assert result == valid_id
