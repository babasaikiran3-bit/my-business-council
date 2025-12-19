"""Conversation management endpoints."""

import uuid
from fastapi import APIRouter, Depends, HTTPException

from .. import storage
from ..auth import AuthenticatedUser, get_current_user
from ..copilot import improve_user_prompt
from .models import (
    Conversation,
    PaginatedConversations,
    ImprovePromptRequest,
)

router = APIRouter(prefix="/api", tags=["conversations"])


@router.post("/improve-prompt")
async def improve_prompt(
    request: ImprovePromptRequest,
    user: AuthenticatedUser = Depends(get_current_user)  # noqa: ARG001
):
    """Improve a user's prompt using an LLM."""
    improved = await improve_user_prompt(request.content)
    return {"improved_prompt": improved}


@router.get("/conversations", response_model=PaginatedConversations)
async def list_conversations(
    limit: int = 10,
    offset: int = 0,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    List conversations for the authenticated user with pagination.

    Args:
        limit: Maximum number of conversations to return (default: 10, max: 50)
        offset: Number of conversations to skip for pagination (default: 0)
    """
    # Enforce reasonable limits
    limit = min(max(1, limit), 50)
    offset = max(0, offset)

    return storage.list_conversations(user_id=user.id, limit=limit, offset=offset)


@router.post("/conversations", response_model=Conversation)
async def create_conversation(user: AuthenticatedUser = Depends(get_current_user)):
    """Create a new conversation for the authenticated user."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id, user_id=user.id)
    return conversation


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id, user_id=user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

