"""Message sending endpoints (batch and streaming)."""

import logging
import time
import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .. import storage
from ..auth import AuthenticatedUser, get_current_user
from ..copilot import (
    run_full_copilot,
    generate_conversation_title,
    stage1_collect_responses_with_progress,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    get_copilot_models,
)
from .models import SendMessageRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["messages"])


@router.post("/{conversation_id}/message")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Send a message and run the 3-stage copilot process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists (scoped to user)
    conversation = storage.get_conversation(conversation_id, user_id=user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message and capture the message ID (needed for assistant response FK)
    user_message_id = storage.add_user_message(
        conversation_id, user_id=user.id, content=request.content
    )

    # Store the original/improved query for first message
    if is_first_message:
        if request.original_query:
            storage.update_conversation_queries(
                conversation_id,
                user_id=user.id,
                original_query=request.original_query,
                improved_query=request.content,
            )
        else:
            storage.update_conversation_queries(
                conversation_id, user_id=user.id, original_query=request.content
            )

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, user_id=user.id, title=title)

    # Run the 3-stage copilot process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_copilot(
        request.content
    )

    # Add assistant response linked to the user message (FK design)
    storage.add_assistant_response(
        user_message_id,  # FK to the user message
        stage1=stage1_results,
        stage2=stage2_results,
        stage3=stage3_result,
        stage1_duration_ms=metadata.get("stage1_duration_ms"),
        stage2_duration_ms=metadata.get("stage2_duration_ms"),
        stage3_duration_ms=metadata.get("stage3_duration_ms"),
        metadata={
            "label_to_model": metadata.get("label_to_model"),
            "aggregate_rankings": metadata.get("aggregate_rankings"),
        },
    )

    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@router.post("/{conversation_id}/message/stream")
async def send_message_stream(
    conversation_id: str,
    request: SendMessageRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Send a message and stream the 3-stage copilot process.
    Returns Server-Sent Events as each stage completes, including individual model completions.
    """
    # Check if conversation exists (scoped to user)
    conversation = storage.get_conversation(conversation_id, user_id=user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Get the list of copilot models for the frontend
    copilot_models = get_copilot_models()

    # Capture values for use in the generator closure
    user_id = user.id
    captured_conversation_id = conversation_id

    logger.info(f"[STREAM] Starting stream for conversation_id={captured_conversation_id}, user_id={user_id}")

    async def event_generator():
        from .streaming import stream_deliberation
        async for event in stream_deliberation(
            conversation_id=captured_conversation_id,
            user_id=user_id,
            request=request,
            is_first_message=is_first_message,
            copilot_models=copilot_models,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        }
    )

