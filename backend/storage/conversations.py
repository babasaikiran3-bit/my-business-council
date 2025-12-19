"""Conversation CRUD operations.

This module handles all conversation-related database operations including
creation, retrieval, listing, and updates.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from supabase import Client

from .client import get_supabase_client
from .search_sync import _safe_index_conversation, _safe_update_conversation_in_index

# Timeout for stale deliberations (10 minutes)
STALE_DELIBERATION_TIMEOUT_MINUTES = 10

logger = logging.getLogger(__name__)


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

    # Index to Typesense for search
    _safe_index_conversation(row)

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
    response_data = row.get("assistant_responses")

    # Handle both dict (1:1) and array (1:N) cases
    response = None
    if isinstance(response_data, dict) and response_data:
        response = response_data
    elif isinstance(response_data, list) and len(response_data) > 0:
        response = response_data[0]

    if response:
        stage3_data = response.get("stage3_synthesis")
        messages.append({
            "role": "assistant",
            "stage1": response.get("stage1_responses") or [],
            "stage2": response.get("stage2_evaluations") or [],
            "stage3": stage3_data if stage3_data else None,
            "response_id": response.get("id"),
            "response_status": response.get("response_status"),
        })

    return messages


def _check_and_mark_stale_deliberations(supabase: Client, conversation_id: str) -> int:
    """
    Check for stale in-progress deliberations and mark them as failed.

    A deliberation is considered stale if it has been in an in-progress status
    for longer than STALE_DELIBERATION_TIMEOUT_MINUTES.

    Returns:
        Number of stale deliberations that were marked as failed
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=STALE_DELIBERATION_TIMEOUT_MINUTES)
    cutoff_iso = cutoff_time.isoformat()

    in_progress_statuses = [
        'pending', 'stage1_in_progress', 'stage1_complete',
        'stage2_in_progress', 'stage2_complete', 'stage3_in_progress'
    ]

    try:
        msg_result = (
            supabase.table("messages")
            .select("id")
            .eq("conversation_id", conversation_id)
            .execute()
        )

        if not msg_result.data:
            return 0

        message_ids = [m["id"] for m in msg_result.data]

        stale_result = (
            supabase.table("assistant_responses")
            .select("id, response_status, created_at")
            .in_("user_message_id", message_ids)
            .in_("response_status", in_progress_statuses)
            .lt("created_at", cutoff_iso)
            .execute()
        )

        if not stale_result.data:
            return 0

        stale_count = 0
        for response in stale_result.data:
            response_id = response["id"]
            old_status = response["response_status"]
            created_at = response["created_at"]

            logger.warning(
                f"[STALE] Marking stale deliberation as failed: "
                f"response_id={response_id}, status={old_status}, created_at={created_at}"
            )

            supabase.table("assistant_responses").update({
                "response_status": "failed",
                "error_details": {
                    "error": f"Deliberation timed out after {STALE_DELIBERATION_TIMEOUT_MINUTES} minutes",
                    "failed_stage": old_status,
                    "timeout_detected_at": datetime.now(timezone.utc).isoformat()
                }
            }).eq("id", response_id).execute()

            stale_count += 1

        return stale_count

    except Exception as e:
        logger.error(f"[STALE] Error checking for stale deliberations: {e}")
        return 0


def get_conversation(conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Also checks for and marks stale deliberations (in-progress for >10 minutes)
    as failed before returning the conversation data.

    Args:
        conversation_id: Unique identifier for the conversation
        user_id: WorkOS user ID for scoping

    Returns:
        Conversation dict with id, created_at, title, messages, or None if not found
    """
    supabase = get_supabase_client()

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

    # Check for and mark stale deliberations
    stale_count = _check_and_mark_stale_deliberations(supabase, conversation_id)
    if stale_count > 0:
        logger.info(f"[STALE] Marked {stale_count} stale deliberation(s) as failed for conversation {conversation_id}")

    msg_result = (
        supabase.table("messages")
        .select("*, assistant_responses(*)")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )

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


def list_conversations(
    user_id: str,
    limit: int = 10,
    offset: int = 0
) -> Dict[str, Any]:
    """
    List conversations for a user with pagination (metadata only).

    Args:
        user_id: WorkOS user ID for scoping
        limit: Maximum number of conversations to return (default: 10)
        offset: Number of conversations to skip (default: 0)

    Returns:
        Dict with 'conversations' list and 'has_more' boolean
    """
    supabase = get_supabase_client()

    conv_result = (
        supabase.table("conversations")
        .select("id, created_at, title, messages(id)")
        .eq("user_id", user_id)
        .eq("is_deleted", False)
        .order("created_at", desc=True)
        .range(offset, offset + limit)
        .execute()
    )

    conversations = []
    data = conv_result.data or []
    has_more = len(data) > limit

    for row in data[:limit]:
        messages_data = row.get("messages", [])
        message_count = len(messages_data) if messages_data else 0

        conversations.append({
            "id": row["id"],
            "created_at": row["created_at"],
            "title": row["title"] or "New Conversation",
            "message_count": message_count,
        })

    return {
        "conversations": conversations,
        "has_more": has_more,
    }


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


def update_conversation_title(conversation_id: str, user_id: str, title: str):
    """
    Update a conversation's title.

    Args:
        conversation_id: Conversation identifier
        user_id: WorkOS user ID for scoping
        title: New title for the conversation
    """
    if not _verify_conversation_ownership(conversation_id, user_id):
        raise ValueError(f"Conversation {conversation_id} not found")

    supabase = get_supabase_client()
    supabase.table("conversations").update({
        "title": title,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", conversation_id).execute()

    # Update Typesense index
    _safe_update_conversation_in_index(conversation_id, {"title": title})


def update_conversation_queries(
    conversation_id: str,
    user_id: str,
    original_query: Optional[str] = None,
    improved_query: Optional[str] = None,
):
    """
    Update a conversation's original and/or improved query.

    Args:
        conversation_id: Conversation identifier
        user_id: WorkOS user ID for scoping
        original_query: Original user query (before improvement)
        improved_query: Improved query (after LLM enhancement)
    """
    if not _verify_conversation_ownership(conversation_id, user_id):
        raise ValueError(f"Conversation {conversation_id} not found")

    supabase = get_supabase_client()
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if original_query is not None:
        update_data["original_query"] = original_query
    if improved_query is not None:
        update_data["improved_query"] = improved_query

    supabase.table("conversations").update(update_data).eq("id", conversation_id).execute()

    # Update Typesense index with original_query if provided
    if original_query is not None:
        _safe_update_conversation_in_index(conversation_id, {"original_query": original_query})

