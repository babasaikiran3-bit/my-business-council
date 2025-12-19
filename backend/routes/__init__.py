"""API route modules for Eternal Copilot."""

from .health import router as health_router
from .search import router as search_router
from .conversations import router as conversations_router
from .messages import router as messages_router
from .responses import router as responses_router

__all__ = [
    "health_router",
    "search_router",
    "conversations_router",
    "messages_router",
    "responses_router",
]

