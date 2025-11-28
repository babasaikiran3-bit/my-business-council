"""Storage module with pluggable backends."""

from typing import Dict, Any, List, Optional
from .base import StorageBackend
from .json_storage import JSONStorageBackend
from ..config import DATA_DIR


# Global storage backend instance
_storage_backend: Optional[StorageBackend] = None


def get_storage_backend() -> StorageBackend:
    """
    Get the configured storage backend.

    Returns:
        Configured storage backend instance
    """
    global _storage_backend

    if _storage_backend is None:
        # For now, always use JSON storage
        # Later, this can be configured via environment variable
        _storage_backend = JSONStorageBackend(DATA_DIR)

    return _storage_backend


def set_storage_backend(backend: StorageBackend) -> None:
    """
    Set the storage backend (useful for testing).

    Args:
        backend: Storage backend instance to use
    """
    global _storage_backend
    _storage_backend = backend


# Backward compatibility functions that delegate to the storage backend
def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """Create a new conversation."""
    return get_storage_backend().create_conversation(conversation_id)


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Get a conversation by ID."""
    return get_storage_backend().get_conversation(conversation_id)


def list_conversations() -> List[Dict[str, Any]]:
    """List all conversations (metadata only)."""
    return get_storage_backend().list_conversations()


def add_user_message(conversation_id: str, content: str) -> None:
    """Add a user message to a conversation."""
    get_storage_backend().add_user_message(conversation_id, content)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
) -> None:
    """Add an assistant message with all council stages."""
    get_storage_backend().add_assistant_message(conversation_id, stage1, stage2, stage3)


def update_conversation_title(conversation_id: str, title: str) -> None:
    """Update the title of a conversation."""
    get_storage_backend().update_conversation_title(conversation_id, title)


def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation."""
    return get_storage_backend().delete_conversation(conversation_id)


def search_conversations(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search conversations by content."""
    return get_storage_backend().search_conversations(query, limit)


def get_conversation_costs(conversation_id: str) -> Dict[str, float]:
    """Get cost statistics for a conversation."""
    return get_storage_backend().get_conversation_costs(conversation_id)


def get_total_costs(start_date=None, end_date=None) -> Dict[str, Any]:
    """Get total costs across all conversations."""
    return get_storage_backend().get_total_costs(start_date, end_date)


__all__ = [
    'StorageBackend',
    'JSONStorageBackend',
    'get_storage_backend',
    'set_storage_backend',
    'create_conversation',
    'get_conversation',
    'list_conversations',
    'add_user_message',
    'add_assistant_message',
    'update_conversation_title',
    'delete_conversation',
    'search_conversations',
    'get_conversation_costs',
    'get_total_costs',
]
