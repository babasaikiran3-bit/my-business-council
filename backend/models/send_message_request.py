"""Request model for sending a message in a conversation."""

from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str

