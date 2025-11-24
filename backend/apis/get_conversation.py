"""Get conversation endpoint."""

from fastapi import APIRouter, HTTPException

from .. import storage
from ..models import Conversation

router = APIRouter()


@router.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

