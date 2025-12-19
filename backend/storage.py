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

Search Integration:
- All CRUD operations automatically sync to Typesense for full-text search
- Indexing is done asynchronously to not block the main request
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from supabase import create_client, Client

from .config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

# Timeout for stale deliberations (10 minutes)
# If a deliberation has been in-progress for longer than this, it's considered stale
# and will be automatically marked as failed when the conversation is loaded.
STALE_DELIBERATION_TIMEOUT_MINUTES = 10

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


# =============================================================================
# Search Indexing Helpers
# =============================================================================


def _safe_index_conversation(conversation: Dict[str, Any]) -> None:
    """Safely index a conversation to Typesense (non-blocking, logs errors)."""
    try:
        from .search import index_conversation, is_typesense_configured

        if is_typesense_configured():
            index_conversation(conversation)
            logger.debug(f"Indexed conversation {conversation['id']} to Typesense")
    except Exception as e:
        # Log but don't fail - search indexing should not block storage operations
        logger.warning(f"Failed to index conversation to Typesense: {e}")


def _safe_index_message(message: Dict[str, Any], user_id: str) -> None:
    """Safely index a message to Typesense (non-blocking, logs errors)."""
    try:
        from .search import index_message, is_typesense_configured

        if is_typesense_configured():
            index_message(message, user_id)
            logger.debug(f"Indexed message {message['id']} to Typesense")
    except Exception as e:
        # Log but don't fail - search indexing should not block storage operations
        logger.warning(f"Failed to index message to Typesense: {e}")


def _safe_update_conversation_in_index(
    conversation_id: str, updates: Dict[str, Any]
) -> None:
    """Safely update a conversation in Typesense (non-blocking, logs errors).

    Note: user_id is not needed here because:
    1. The document was created with the correct user_id
    2. We're only updating fields like title/original_query
    3. user_id should never change after creation
    """
    try:
        from .search import get_typesense_client, is_typesense_configured

        if is_typesense_configured():
            client = get_typesense_client()
            # Typesense upsert with partial update
            client.collections["conversations"].documents[conversation_id].update(
                updates
            )
            logger.debug(f"Updated conversation {conversation_id} in Typesense")
    except Exception as e:
        # Log but don't fail
        logger.warning(f"Failed to update conversation in Typesense: {e}")


# =============================================================================
# Conversation CRUD Operations
# =============================================================================


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
        # Only include stage3 if it has actual data (not None or empty)
        # This prevents "Chairman: Unknown" from showing for incomplete responses
        stage3_data = response.get("stage3_synthesis")
        messages.append({
            "role": "assistant",
            "stage1": response.get("stage1_responses") or [],
            "stage2": response.get("stage2_evaluations") or [],
            "stage3": stage3_data if stage3_data else None,
            # Include response metadata for recovery of in-progress deliberations
            "response_id": response.get("id"),
            "response_status": response.get("response_status"),
        })

    return messages


def _check_and_mark_stale_deliberations(supabase: Client, conversation_id: str) -> int:
    """
    Check for stale in-progress deliberations and mark them as failed.

    A deliberation is considered stale if it has been in an in-progress status
    for longer than STALE_DELIBERATION_TIMEOUT_MINUTES.

    Args:
        supabase: Supabase client
        conversation_id: The conversation to check

    Returns:
        Number of stale deliberations that were marked as failed
    """
    # Calculate the cutoff time
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=STALE_DELIBERATION_TIMEOUT_MINUTES)
    cutoff_iso = cutoff_time.isoformat()

    # In-progress statuses that indicate a deliberation is still running
    in_progress_statuses = [
        'pending', 'stage1_in_progress', 'stage1_complete',
        'stage2_in_progress', 'stage2_complete', 'stage3_in_progress'
    ]

    # Find stale responses for this conversation
    # We need to join through messages to filter by conversation_id
    try:
        # First, get all message IDs for this conversation
        msg_result = (
            supabase.table("messages")
            .select("id")
            .eq("conversation_id", conversation_id)
            .execute()
        )

        if not msg_result.data:
            return 0

        message_ids = [m["id"] for m in msg_result.data]

        # Find stale responses
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

        # Mark each stale response as failed
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

    # Check for and mark stale deliberations before fetching messages
    # This ensures the frontend sees the correct 'failed' status for timed-out deliberations
    stale_count = _check_and_mark_stale_deliberations(supabase, conversation_id)
    if stale_count > 0:
        logger.info(f"[STALE] Marked {stale_count} stale deliberation(s) as failed for conversation {conversation_id}")

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

    # Fetch conversations with message counts using a nested select
    # This avoids N+1 queries by getting messages in a single request
    # Request one extra to determine if there are more results
    conv_result = (
        supabase.table("conversations")
        .select("id, created_at, title, messages(id)")
        .eq("user_id", user_id)
        .eq("is_deleted", False)
        .order("created_at", desc=True)
        .range(offset, offset + limit)  # Supabase range is inclusive
        .execute()
    )

    conversations = []
    data = conv_result.data or []

    # Check if there are more results (we requested limit+1 to check)
    has_more = len(data) > limit

    # Only process up to 'limit' items
    for row in data[:limit]:
        # Count messages from the nested select result
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

    # Index message to Typesense for search
    message_row = result.data[0]
    message_row["conversation_id"] = conversation_id  # Ensure it's included
    _safe_index_message(message_row, user_id)

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
        "response_status": "pending",  # Will be updated as stages progress
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
            "response_status": "stage1_complete",
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
        "response_status": "stage2_complete",
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

    Also cleans up partial stage responses since the aggregated data
    is now saved and we don't need the granular per-model rows.

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
            "response_status": "complete",
        })
        .eq("id", response_id)
        .execute()
    )

    if not result.data:
        raise RuntimeError(f"Failed to update response stage3: {result}")

    # Clean up partial stage responses since we're now complete
    cleanup_partial_stage_responses(response_id)


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

    # Update Typesense index
    _safe_update_conversation_in_index(conversation_id, {"title": title})


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

    # Update Typesense index with original_query (searchable field)
    if original_query is not None:
        _safe_update_conversation_in_index(
            conversation_id, {"original_query": original_query}
        )


# =============================================================================
# Incremental Persistence for Model Responses
# =============================================================================


def update_response_status(response_id: str, status: str):
    """
    Update the response_status of an assistant response.

    Valid statuses:
        - 'pending': Just created, no stages started
        - 'stage1_in_progress': Stage 1 running
        - 'stage1_complete': Stage 1 done
        - 'stage2_in_progress': Stage 2 running
        - 'stage2_complete': Stage 2 done
        - 'stage3_in_progress': Stage 3 running
        - 'complete': All stages done
        - 'failed': Deliberation failed

    Args:
        response_id: The assistant response ID
        status: New status value
    """
    supabase = get_supabase_client()

    result = (
        supabase.table("assistant_responses")
        .update({"response_status": status})
        .eq("id", response_id)
        .execute()
    )

    if not result.data:
        raise RuntimeError(f"Failed to update response status: {result}")


def set_response_error(response_id: str, error_message: str, error_stage: str):
    """
    Mark a response as failed with error details.

    Args:
        response_id: The assistant response ID
        error_message: Human-readable error message
        error_stage: Which stage failed ('stage1', 'stage2', 'stage3')
    """
    supabase = get_supabase_client()

    result = (
        supabase.table("assistant_responses")
        .update({
            "response_status": "failed",
            "error_details": {
                "message": error_message,
                "stage": error_stage,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        })
        .eq("id", response_id)
        .execute()
    )

    if not result.data:
        raise RuntimeError(f"Failed to set response error: {result}")


def save_model_response(
    assistant_response_id: str,
    stage: int,
    model_name: str,
    response_content: Optional[Dict[str, Any]],
    elapsed_ms: int,
    success: bool,
    error_message: Optional[str] = None,
):
    """
    Save an individual model response as it completes during Stage 1.

    This enables incremental persistence - if Stage 1 fails after some models
    have responded, smart retry can reuse the saved responses.

    Args:
        assistant_response_id: The assistant response this belongs to
        stage: Stage number (1, 2, or 3)
        model_name: Model identifier (e.g., 'openai/gpt-5.2-pro')
        response_content: The model's response (JSONB)
        elapsed_ms: Time taken for this model to respond
        success: Whether the model responded successfully
        error_message: Error message if failed
    """
    supabase = get_supabase_client()

    data = {
        "assistant_response_id": assistant_response_id,
        "stage": stage,
        "model_name": model_name,
        "response_content": response_content,
        "elapsed_ms": elapsed_ms,
        "status": "success" if success else "failed",
        "error_message": error_message,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Use upsert to handle retries (unique constraint on assistant_response_id, stage, model_name)
    result = (
        supabase.table("stage_model_responses")
        .upsert(data, on_conflict="assistant_response_id,stage,model_name")
        .execute()
    )

    if not result.data:
        raise RuntimeError(f"Failed to save model response: {result}")

    return result.data[0]["id"]


def get_partial_stage_responses(
    assistant_response_id: str,
    stage: int,
) -> List[Dict[str, Any]]:
    """
    Get all successful model responses for a stage.

    Used for smart retry to reuse responses from models that already completed.

    Args:
        assistant_response_id: The assistant response ID
        stage: Stage number (1, 2, or 3)

    Returns:
        List of model response dicts with model_name, response_content, elapsed_ms
    """
    supabase = get_supabase_client()

    result = (
        supabase.table("stage_model_responses")
        .select("model_name, response_content, elapsed_ms")
        .eq("assistant_response_id", assistant_response_id)
        .eq("stage", stage)
        .eq("status", "success")
        .order("completed_at")
        .execute()
    )

    return result.data or []


def get_response_with_partial_stages(
    response_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get an assistant response with its partial stage data.

    Used to retrieve incomplete responses for smart retry.

    Args:
        response_id: The assistant response ID

    Returns:
        Dict with response data and partial_stages, or None if not found
    """
    supabase = get_supabase_client()

    # Get the response
    response_result = (
        supabase.table("assistant_responses")
        .select("*")
        .eq("id", response_id)
        .execute()
    )

    if not response_result.data:
        return None

    response = response_result.data[0]

    # Get partial stage responses
    partial_result = (
        supabase.table("stage_model_responses")
        .select("stage, model_name, response_content, elapsed_ms, status")
        .eq("assistant_response_id", response_id)
        .order("stage, completed_at")
        .execute()
    )

    # Group by stage
    partial_stages: Dict[int, List[Dict]] = {1: [], 2: [], 3: []}
    for row in (partial_result.data or []):
        stage = row["stage"]
        if stage in partial_stages:
            partial_stages[stage].append({
                "model_name": row["model_name"],
                "response_content": row["response_content"],
                "elapsed_ms": row["elapsed_ms"],
                "status": row["status"],
            })

    return {
        "response": response,
        "partial_stages": partial_stages,
    }


def cleanup_partial_stage_responses(assistant_response_id: str):
    """
    Delete partial stage responses after a response completes successfully.

    The aggregated data is already in assistant_responses.stage1/2/3_*,
    so we can remove the granular per-model rows to save space.

    Args:
        assistant_response_id: The assistant response ID
    """
    supabase = get_supabase_client()

    try:
        supabase.table("stage_model_responses").delete().eq(
            "assistant_response_id", assistant_response_id
        ).execute()
    except Exception as e:
        # Log but don't fail - this is cleanup, not critical path
        logger.warning(
            f"Failed to cleanup partial stage responses for {assistant_response_id}: {e}"
        )


def get_incomplete_responses_for_conversation(
    conversation_id: str,
    user_id: str,
) -> List[Dict[str, Any]]:
    """
    Get all incomplete assistant responses for a conversation.

    Used to detect if there are any in-progress or failed responses
    that could be resumed.

    Args:
        conversation_id: The conversation ID
        user_id: WorkOS user ID for scoping

    Returns:
        List of incomplete response dicts
    """
    supabase = get_supabase_client()

    # First verify conversation ownership
    if not _verify_conversation_ownership(conversation_id, user_id):
        raise ValueError(f"Conversation {conversation_id} not found")

    # Get message IDs for this conversation
    msg_result = (
        supabase.table("messages")
        .select("id")
        .eq("conversation_id", conversation_id)
        .execute()
    )

    if not msg_result.data:
        return []

    message_ids = [m["id"] for m in msg_result.data]

    # Get incomplete responses for these messages
    response_result = (
        supabase.table("assistant_responses")
        .select("id, user_message_id, response_status, error_details, created_at")
        .in_("user_message_id", message_ids)
        .neq("response_status", "complete")
        .order("created_at", desc=True)
        .execute()
    )

    return response_result.data or []
