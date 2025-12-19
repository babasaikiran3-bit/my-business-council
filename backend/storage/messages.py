"""Message operations.

This module handles user message creation and retrieval.
In the FK design, only user messages are stored in the messages table.
Assistant responses are stored in a separate table with a FK to the user message.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from .client import get_supabase_client
from .conversations import _verify_conversation_ownership
from .search_sync import _safe_index_message

logger = logging.getLogger(__name__)


def add_user_message(conversation_id: str, user_id: str, content: str) -> str:
    """
    Add a user message to a conversation.

    In the FK design, messages table only contains user messages.
    Assistant responses are stored in the assistant_responses table
    with a foreign key to the user message.

    Args:
        conversation_id: Conversation identifier
        user_id: WorkOS user ID for scoping
        content: User message content

    Returns:
        The ID of the created message (used as FK for assistant_responses)
    """
    if not _verify_conversation_ownership(conversation_id, user_id):
        raise ValueError(f"Conversation {conversation_id} not found")

    supabase = get_supabase_client()

    message_data = {
        "conversation_id": conversation_id,
        "content": content,
    }

    result = supabase.table("messages").insert(message_data).execute()

    if not result.data:
        raise RuntimeError(f"Failed to add user message: {result}")

    # Update conversation's updated_at timestamp
    supabase.table("conversations").update(
        {"updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", conversation_id).execute()

    # Index message to Typesense for search
    message_row = result.data[0]
    message_row["conversation_id"] = conversation_id
    _safe_index_message(message_row, user_id)

    return result.data[0]["id"]

