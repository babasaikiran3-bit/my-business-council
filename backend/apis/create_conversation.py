"""Create conversation endpoint."""

import uuid
from fastapi import APIRouter

from .. import storage
from ..models import CreateConversationRequest, Conversation

router = APIRouter()


@router.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation
