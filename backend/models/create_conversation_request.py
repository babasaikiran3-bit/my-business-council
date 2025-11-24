"""Request model for creating a new conversation."""

from pydantic import BaseModel


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass

