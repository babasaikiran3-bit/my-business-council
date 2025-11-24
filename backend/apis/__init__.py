"""API endpoints for LLM Council."""

from fastapi import APIRouter

from .root import router as root_router
from .list_conversations import router as list_conversations_router
from .create_conversation import router as create_conversation_router
from .get_conversation import router as get_conversation_router
from .send_message import router as send_message_router
from .send_message_stream import router as send_message_stream_router

# Create main API router
api_router = APIRouter()

# Include all routers
api_router.include_router(root_router)
api_router.include_router(list_conversations_router)
api_router.include_router(create_conversation_router)
api_router.include_router(get_conversation_router)
api_router.include_router(send_message_router)
api_router.include_router(send_message_stream_router)

__all__ = ["api_router"]
