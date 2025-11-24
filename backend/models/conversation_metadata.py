"""Model for conversation metadata in list view."""

from pydantic import BaseModel


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int

