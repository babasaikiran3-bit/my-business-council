"""Assistant response operations.

This module handles all assistant response operations including:
- Creating response placeholders for incremental updates
- Updating responses with stage results
- Managing response status and errors
- Incremental persistence for model responses (smart retry)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .client import get_supabase_client
from .conversations import _verify_conversation_ownership

logger = logging.getLogger(__name__)


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
    incremental saves as each stage completes.

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
        "response_status": "pending",
    }

    result = supabase.table("assistant_responses").insert(response_data).execute()

    if not result.data:
        raise RuntimeError(f"Failed to create response placeholder: {result}")

    return result.data[0]["id"]


def delete_response_placeholder(response_id: str) -> bool:
    """
    Delete an incomplete assistant response placeholder.

    Called when an error occurs during streaming to clean up the empty placeholder.

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
        print(f"Warning: Failed to delete response placeholder {response_id}: {e}")
        return False


def update_response_stage1(
    response_id: str,
    stage1_responses: List[Dict[str, Any]],
    stage1_duration_ms: int,
):
    """Update an assistant response with Stage 1 results."""
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
    """Update an assistant response with Stage 2 results."""
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

    # Use upsert to handle retries
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
    """
    supabase = get_supabase_client()

    response_result = (
        supabase.table("assistant_responses")
        .select("*")
        .eq("id", response_id)
        .execute()
    )

    if not response_result.data:
        return None

    response = response_result.data[0]

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
    """
    supabase = get_supabase_client()

    try:
        supabase.table("stage_model_responses").delete().eq(
            "assistant_response_id", assistant_response_id
        ).execute()
    except Exception as e:
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
    """
    supabase = get_supabase_client()

    if not _verify_conversation_ownership(conversation_id, user_id):
        raise ValueError(f"Conversation {conversation_id} not found")

    msg_result = (
        supabase.table("messages")
        .select("id")
        .eq("conversation_id", conversation_id)
        .execute()
    )

    if not msg_result.data:
        return []

    message_ids = [m["id"] for m in msg_result.data]

    response_result = (
        supabase.table("assistant_responses")
        .select("id, user_message_id, response_status, error_details, created_at")
        .in_("user_message_id", message_ids)
        .neq("response_status", "complete")
        .order("created_at", desc=True)
        .execute()
    )

    return response_result.data or []

