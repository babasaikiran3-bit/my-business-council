"""Typesense search sync helpers.

These helper functions safely index storage operations to Typesense for full-text search.
All operations are non-blocking - failures are logged but don't affect storage operations.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _safe_index_conversation(conversation: Dict[str, Any]) -> None:
    """Safely index a conversation to Typesense (non-blocking, logs errors)."""
    try:
        from ..search import index_conversation, is_typesense_configured

        if is_typesense_configured():
            index_conversation(conversation)
            logger.debug(f"Indexed conversation {conversation['id']} to Typesense")
    except Exception as e:
        # Log but don't fail - search indexing should not block storage operations
        logger.warning(f"Failed to index conversation to Typesense: {e}")


def _safe_index_message(message: Dict[str, Any], user_id: str) -> None:
    """Safely index a message to Typesense (non-blocking, logs errors)."""
    try:
        from ..search import index_message, is_typesense_configured

        if is_typesense_configured():
            index_message(message, user_id)
            logger.debug(f"Indexed message {message['id']} to Typesense")
    except Exception as e:
        # Log but don't fail - search indexing should not block storage operations
        logger.warning(f"Failed to index message to Typesense: {e}")


def _safe_update_conversation_in_index(
    conversation_id: str,
    updates: Dict[str, Any],
) -> None:
    """Safely update a conversation in Typesense index (non-blocking, logs errors)."""
    try:
        from ..search import is_typesense_configured, get_typesense_client

        if is_typesense_configured():
            client = get_typesense_client()
            # Typesense update requires the full document with id
            update_doc = {"id": conversation_id, **updates}
            client.collections["conversations"].documents[conversation_id].update(update_doc)
            logger.debug(f"Updated conversation {conversation_id} in Typesense")
    except Exception as e:
        # Log but don't fail - search indexing should not block storage operations
        logger.warning(f"Failed to update conversation in Typesense: {e}")

