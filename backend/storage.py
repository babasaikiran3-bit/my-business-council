"""Supabase-backed storage for conversations.

This module provides user-scoped conversation storage using Supabase PostgreSQL.
It maintains backward compatibility with the previous JSON file-based API.

Database Schema:
- conversations: id, user_id, organization_id, title, original_query, improved_query, timestamps
- messages: id, conversation_id, content (user queries only)
- assistant_responses: id, user_message_id (FK), stage1/2/3 data, timing metrics
- conversation_shares: For future collaboration features

The FK design provides:
- Explicit 1:1 relationship between user messages and assistant responses
- Data integrity via foreign key constraints with CASCADE delete
- Clean separation of user queries from AI responses
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from supabase import create_client, Client

from .config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)

# Supabase client singleton
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Get or create Supabase client singleton."""
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client


def create_conversation(
    conversation_id: str,
    user_id: str,
    organization_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new conversation for a user.

    Args:
        conversation_id: Unique identifier for the conversation
        user_id: WorkOS user ID for scoping
        organization_id: Optional organization ID for future sharing

    Returns:
        New conversation dict with id, user_id, created_at, title, messages
    """
    supabase = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    conversation_data = {
        "id": conversation_id,
        "user_id": user_id,
        "organization_id": organization_id,
        "title": "New Conversation",
        "created_at": now,
        "updated_at": now,
    }

    result = supabase.table("conversations").insert(conversation_data).execute()

    if not result.data:
        raise RuntimeError(f"Failed to create conversation: {result}")

    row = result.data[0]
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "created_at": row["created_at"],
        "title": row["title"],
        "messages": [],
    }


def _convert_joined_row_to_messages(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert a JOINed row (user message + nested assistant response) into message dicts.

    The row structure from Supabase nested select depends on the FK constraint:
    - With UNIQUE constraint (1:1): assistant_responses is a single dict or None
    - Without UNIQUE constraint (1:N): assistant_responses is an array

    {
        "id": "user-msg-id",
        "content": "What is ML?",
        "created_at": "...",
        "assistant_responses": {           # Single dict for 1:1 (UNIQUE FK)
            "stage1_responses": [...],
            "stage2_evaluations": [...],
            "stage3_synthesis": {...},
        }
    }

    Returns a list of 1-2 message dicts:
    - Always includes the user message
    - Includes assistant message if response exists
    """
    messages = []

    # Always add the user message
    messages.append({
        "role": "user",
        "content": row["content"],
    })

    # Add assistant message if response exists
    # Supabase returns single dict for 1:1 relationship (UNIQUE FK constraint)
    response_data = row.get("assistant_responses")

    # Handle both dict (1:1) and array (1:N) cases
    response = None
    if isinstance(response_data, dict) and response_data:
        # 1:1 relationship returns a single dict
        response = response_data
    elif isinstance(response_data, list) and len(response_data) > 0:
        # 1:N relationship returns an array
        response = response_data[0]

    if response:
        messages.append({
            "role": "assistant",
            "stage1": response.get("stage1_responses") or [],
            "stage2": response.get("stage2_evaluations") or [],
            "stage3": response.get("stage3_synthesis") or {},
        })

    return messages


def get_conversation(conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation
        user_id: WorkOS user ID for scoping

    Returns:
        Conversation dict with id, created_at, title, messages, or None if not found
    """
    supabase = get_supabase_client()

    # Fetch conversation (user_id check for authorization)
    conv_result = (
        supabase.table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .eq("is_deleted", False)
        .execute()
    )

    if not conv_result.data:
        return None

    conv_row = conv_result.data[0]

    # Fetch messages with nested assistant responses using Supabase nested select
    # This performs a LEFT JOIN automatically via the FK relationship
    msg_result = (
        supabase.table("messages")
        .select("*, assistant_responses(*)")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )

    # Flatten joined rows into alternating user/assistant messages
    messages = []
    for row in (msg_result.data or []):
        messages.extend(_convert_joined_row_to_messages(row))

    return {
        "id": conv_row["id"],
        "user_id": conv_row["user_id"],
        "created_at": conv_row["created_at"],
        "title": conv_row["title"] or "New Conversation",
        "messages": messages,
    }


def list_conversations(user_id: str) -> List[Dict[str, Any]]:
    """
    List all conversations for a user (metadata only).

    Args:
        user_id: WorkOS user ID for scoping

    Returns:
        List of conversation metadata dicts with id, created_at, title, message_count
    """
    supabase = get_supabase_client()

    # Fetch conversations with message counts using a join
    # We'll get all conversations and then count messages in Python for simplicity
    conv_result = (
        supabase.table("conversations")
        .select("id, created_at, title")
        .eq("user_id", user_id)
        .eq("is_deleted", False)
        .order("created_at", desc=True)
        .execute()
    )

    conversations = []
    for row in conv_result.data or []:
        # Count messages for each conversation
        msg_count_result = (
            supabase.table("messages")
            .select("id", count="exact")
            .eq("conversation_id", row["id"])
            .execute()
        )
        message_count = msg_count_result.count if msg_count_result.count else 0

        conversations.append({
            "id": row["id"],
            "created_at": row["created_at"],
            "title": row["title"] or "New Conversation",
            "message_count": message_count,
        })

    return conversations


def _verify_conversation_ownership(conversation_id: str, user_id: str) -> bool:
    """Verify that user owns the conversation."""
    supabase = get_supabase_client()
    result = (
        supabase.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .eq("is_deleted", False)
        .execute()
    )
    return bool(result.data)


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

    # In FK design, messages table has no 'role' column - all messages are user messages
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

    return result.data[0]["id"]


def add_assistant_response(
    user_message_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    stage1_duration_ms: Optional[int] = None,
    stage2_duration_ms: Optional[int] = None,
    stage3_duration_ms: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Add an assistant response with all 3 stages linked to a user message.

    In the FK design, assistant responses are stored in a separate table
    with a foreign key to the user message.

    Args:
        user_message_id: The ID of the user message this response is for
        stage1: List of individual model responses
        stage2: List of model rankings/evaluations
        stage3: Final synthesized response
        stage1_duration_ms: Time taken for Stage 1 in milliseconds
        stage2_duration_ms: Time taken for Stage 2 in milliseconds
        stage3_duration_ms: Time taken for Stage 3 in milliseconds
        metadata: Additional metadata (label_to_model, aggregate_rankings)

    Returns:
        The ID of the created assistant response
    """
    supabase = get_supabase_client()

    response_data = {
        "user_message_id": user_message_id,
        "stage1_responses": stage1,
        "stage2_evaluations": stage2,
        "stage3_synthesis": stage3,
        "stage1_duration_ms": stage1_duration_ms,
        "stage2_duration_ms": stage2_duration_ms,
        "stage3_duration_ms": stage3_duration_ms,
        "metadata": metadata,
    }

    result = supabase.table("assistant_responses").insert(response_data).execute()

    if not result.data:
        raise RuntimeError(f"Failed to add assistant response: {result}")

    return result.data[0]["id"]


def create_response_placeholder(user_message_id: str) -> str:
    """
    Create an empty assistant response placeholder for incremental updates.

    This is used to reserve a response slot before Stage 1 begins, allowing
    incremental saves as each stage completes. The response is linked to
    the user message via foreign key.

    Args:
        user_message_id: The ID of the user message this response is for

    Returns:
        The ID of the created placeholder response
    """
    supabase = get_supabase_client()

    response_data = {
        "user_message_id": user_message_id,
        "stage1_responses": None,
        "stage2_evaluations": None,
        "stage3_synthesis": None,
    }

    result = supabase.table("assistant_responses").insert(response_data).execute()

    if not result.data:
        raise RuntimeError(f"Failed to create response placeholder: {result}")

    return result.data[0]["id"]


def delete_response_placeholder(response_id: str) -> bool:
    """
    Delete an incomplete assistant response placeholder.

    This is called when an error occurs during the streaming process to clean up
    the empty placeholder that was created at the start of the stream. This prevents
    "Chairman: Unknown" from showing in the UI.

    Args:
        response_id: The assistant response ID to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("assistant_responses")
            .delete()
            .eq("id", response_id)
            .execute()
        )
        return len(result.data) > 0
    except Exception as e:
        # Log but don't raise - this is cleanup, main error already happened
        print(f"Warning: Failed to delete response placeholder {response_id}: {e}")
        return False


def update_response_stage1(
    response_id: str,
    stage1_responses: List[Dict[str, Any]],
    stage1_duration_ms: int,
):
    """
    Update an assistant response with Stage 1 results.

    Args:
        response_id: The assistant response ID to update
        stage1_responses: List of individual model responses
        stage1_duration_ms: Time taken for Stage 1 in milliseconds
    """
    supabase = get_supabase_client()

    result = (
        supabase.table("assistant_responses")
        .update({
            "stage1_responses": stage1_responses,
            "stage1_duration_ms": stage1_duration_ms,
        })
        .eq("id", response_id)
        .execute()
    )

    if not result.data:
        raise RuntimeError(f"Failed to update response stage1: {result}")


def update_response_stage2(
    response_id: str,
    stage2_evaluations: List[Dict[str, Any]],
    stage2_duration_ms: int,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Update an assistant response with Stage 2 results.

    Args:
        response_id: The assistant response ID to update
        stage2_evaluations: List of model rankings/evaluations
        stage2_duration_ms: Time taken for Stage 2 in milliseconds
        metadata: Additional metadata (label_to_model, aggregate_rankings)
    """
    supabase = get_supabase_client()

    update_data = {
        "stage2_evaluations": stage2_evaluations,
        "stage2_duration_ms": stage2_duration_ms,
    }
    if metadata is not None:
        update_data["metadata"] = metadata

    result = (
        supabase.table("assistant_responses")
        .update(update_data)
        .eq("id", response_id)
        .execute()
    )

    if not result.data:
        raise RuntimeError(f"Failed to update response stage2: {result}")


def update_response_stage3(
    response_id: str,
    stage3_synthesis: Dict[str, Any],
    stage3_duration_ms: int,
):
    """
    Update an assistant response with Stage 3 results.

    Args:
        response_id: The assistant response ID to update
        stage3_synthesis: Final synthesized response
        stage3_duration_ms: Time taken for Stage 3 in milliseconds
    """
    supabase = get_supabase_client()

    result = (
        supabase.table("assistant_responses")
        .update({
            "stage3_synthesis": stage3_synthesis,
            "stage3_duration_ms": stage3_duration_ms,
        })
        .eq("id", response_id)
        .execute()
    )

    if not result.data:
        raise RuntimeError(f"Failed to update response stage3: {result}")


def update_conversation_title(conversation_id: str, user_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        user_id: WorkOS user ID for scoping
        title: New title for the conversation
    """
    supabase = get_supabase_client()

    # Update with user_id check for authorization
    result = (
        supabase.table("conversations")
        .update({"title": title})
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise ValueError(f"Conversation {conversation_id} not found")


def update_conversation_queries(
    conversation_id: str,
    user_id: str,
    original_query: Optional[str] = None,
    improved_query: Optional[str] = None,
):
    """
    Update the original and/or improved query for a conversation.

    Args:
        conversation_id: Conversation identifier
        user_id: WorkOS user ID for scoping
        original_query: The original user query
        improved_query: The LLM-improved query (if any)
    """
    supabase = get_supabase_client()

    update_data = {}
    if original_query is not None:
        update_data["original_query"] = original_query
    if improved_query is not None:
        update_data["improved_query"] = improved_query

    if not update_data:
        return

    result = (
        supabase.table("conversations")
        .update(update_data)
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise ValueError(f"Conversation {conversation_id} not found")
