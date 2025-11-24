"""Model for full conversation with all messages."""

from typing import List, Dict, Any
from pydantic import BaseModel


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]

