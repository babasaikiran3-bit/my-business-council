"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, field_validator
from typing import List, Dict, Any


# Maximum allowed content length for messages (100KB should be plenty for any reasonable query)
MAX_CONTENT_LENGTH = 100_000


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    original_query: str | None = None  # Original user-typed query (before improvement)
    # For smart retry: skip stages that already completed successfully
    stage1_data: list | None = None  # Completed Stage 1 responses to reuse
    stage2_data: list | None = None  # Completed Stage 2 rankings to reuse
    stage2_metadata: dict | None = None  # label_to_model and aggregate_rankings from Stage 2

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate that content is not empty and not excessively long."""
        if not v or not v.strip():
            raise ValueError('Message content cannot be empty')
        if len(v) > MAX_CONTENT_LENGTH:
            raise ValueError(f'Message content exceeds maximum length of {MAX_CONTENT_LENGTH:,} characters')
        return v.strip()

    @field_validator('original_query')
    @classmethod
    def validate_original_query(cls, v: str | None) -> str | None:
        """Validate original_query if provided."""
        if v is None:
            return v
        if len(v) > MAX_CONTENT_LENGTH:
            raise ValueError(f'Original query exceeds maximum length of {MAX_CONTENT_LENGTH:,} characters')
        return v.strip() if v.strip() else None


class ImprovePromptRequest(BaseModel):
    """Request to improve a prompt."""
    content: str

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate that content is not empty and not excessively long."""
        if not v or not v.strip():
            raise ValueError('Prompt content cannot be empty')
        if len(v) > MAX_CONTENT_LENGTH:
            raise ValueError(f'Prompt content exceeds maximum length of {MAX_CONTENT_LENGTH:,} characters')
        return v.strip()


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class PaginatedConversations(BaseModel):
    """Paginated list of conversations."""
    conversations: List[ConversationMetadata]
    has_more: bool


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]

