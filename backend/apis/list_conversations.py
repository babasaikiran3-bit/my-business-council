"""List conversations endpoint."""

from typing import List
from fastapi import APIRouter

from .. import storage
from ..models import ConversationMetadata

router = APIRouter()


@router.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()

