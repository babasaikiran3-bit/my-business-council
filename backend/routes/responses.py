"""Response management endpoints (partial stages, cancel, resume)."""

import logging
import time
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .. import storage
from ..auth import AuthenticatedUser, get_current_user
from ..copilot import get_copilot_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/responses", tags=["responses"])


@router.get("/{response_id}/partial-stages")
async def get_partial_stages(
    response_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Get partial stage data for a response (for smart retry).

    Returns the response status and any partial model responses that were
    saved before the deliberation failed.
    """
    result = storage.get_response_with_partial_stages(response_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Response not found")

    # Verify user owns this response by checking the conversation ownership
    response = result["response"]
    user_message_id = response.get("user_message_id")
    if not user_message_id:
        raise HTTPException(status_code=404, detail="Response not found")

    # Get the message to find the conversation
    supabase = storage.get_supabase_client()
    msg_result = (
        supabase.table("messages")
        .select("conversation_id")
        .eq("id", user_message_id)
        .execute()
    )
    if not msg_result.data:
        raise HTTPException(status_code=404, detail="Response not found")

    conv_id = msg_result.data[0]["conversation_id"]
    if not storage._verify_conversation_ownership(conv_id, user.id):
        raise HTTPException(status_code=404, detail="Response not found")

    return {
        "response_id": response_id,
        "response_status": response.get("response_status", "unknown"),
        "error_details": response.get("error_details"),
        "stage1_responses": response.get("stage1_responses"),
        "stage2_evaluations": response.get("stage2_evaluations"),
        "metadata": response.get("metadata"),
        "partial_stages": result["partial_stages"],
    }


@router.post("/{response_id}/cancel")
async def cancel_response(
    response_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Cancel/abort a stale or orphaned deliberation.

    This endpoint marks an in-progress response as 'failed' so the user can retry.
    """
    supabase = storage.get_supabase_client()

    # Fetch the response to check its current status and verify ownership
    response_result = (
        supabase.table("assistant_responses")
        .select("id, response_status, user_message_id")
        .eq("id", response_id)
        .execute()
    )

    if not response_result.data:
        raise HTTPException(status_code=404, detail="Response not found")

    response = response_result.data[0]

    # Verify ownership by checking the conversation belongs to this user
    msg_result = (
        supabase.table("messages")
        .select("conversation_id")
        .eq("id", response["user_message_id"])
        .execute()
    )

    if not msg_result.data:
        raise HTTPException(status_code=404, detail="Response not found")

    conv_id = msg_result.data[0]["conversation_id"]
    if not storage._verify_conversation_ownership(conv_id, user.id):
        raise HTTPException(status_code=404, detail="Response not found")

    # Check if the response is in an in-progress state
    in_progress_statuses = [
        'pending', 'stage1_in_progress', 'stage1_complete',
        'stage2_in_progress', 'stage2_complete', 'stage3_in_progress'
    ]

    current_status = response.get("response_status")
    if current_status not in in_progress_statuses:
        if current_status == 'complete':
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel a completed deliberation"
            )
        elif current_status == 'failed':
            return {
                "success": True,
                "response_id": response_id,
                "previous_status": current_status,
                "new_status": "failed",
                "message": "Deliberation was already marked as failed"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel deliberation with status: {current_status}"
            )

    # Mark the response as failed
    storage.update_response_status(response_id, "failed")

    # Also set error details to indicate manual cancellation
    try:
        supabase.table("assistant_responses").update({
            "error_details": {
                "error": "Deliberation was manually cancelled",
                "failed_stage": current_status,
                "cancelled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        }).eq("id", response_id).execute()
    except Exception as e:
        logger.warning(f"Failed to set error details for cancelled response {response_id}: {e}")

    logger.info(f"[CANCEL] Response {response_id} cancelled by user {user.id} (was {current_status})")

    return {
        "success": True,
        "response_id": response_id,
        "previous_status": current_status,
        "new_status": "failed",
        "message": "Deliberation cancelled successfully"
    }


@router.post("/{response_id}/resume")
async def resume_response(
    response_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Resume a failed deliberation from the last completed stage.

    This endpoint checks which stages have already been completed for a failed
    response and streams the remaining stages. It reuses persisted stage data
    to avoid duplicate API calls.

    Returns SSE stream with the remaining stages.
    """
    supabase = storage.get_supabase_client()

    # Fetch the response to check its current status
    response_result = (
        supabase.table("assistant_responses")
        .select("*")
        .eq("id", response_id)
        .execute()
    )

    if not response_result.data:
        raise HTTPException(status_code=404, detail="Response not found")

    response = response_result.data[0]

    # Verify ownership by checking the conversation belongs to this user
    user_message_id = response.get("user_message_id")
    if not user_message_id:
        raise HTTPException(status_code=404, detail="Response not found")

    msg_result = (
        supabase.table("messages")
        .select("conversation_id, content")
        .eq("id", user_message_id)
        .execute()
    )

    if not msg_result.data:
        raise HTTPException(status_code=404, detail="Response not found")

    conv_id = msg_result.data[0]["conversation_id"]
    user_query = msg_result.data[0]["content"]

    if not storage._verify_conversation_ownership(conv_id, user.id):
        raise HTTPException(status_code=404, detail="Response not found")

    # Check if the response is in a failed state
    current_status = response.get("response_status")
    if current_status != 'failed':
        if current_status == 'complete':
            raise HTTPException(
                status_code=400,
                detail="Cannot resume a completed deliberation"
            )
        elif current_status in ['pending', 'stage1_in_progress', 'stage2_in_progress', 'stage3_in_progress']:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot resume - deliberation is still in progress ({current_status})"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot resume deliberation with status: {current_status}"
            )

    # Determine which stages are already complete
    stage1_responses = response.get("stage1_responses")
    stage2_evaluations = response.get("stage2_evaluations")
    stage3_synthesis = response.get("stage3_synthesis")
    metadata = response.get("metadata")

    # Determine resume point
    if stage3_synthesis:
        raise HTTPException(
            status_code=400,
            detail="All stages are already complete. Nothing to resume."
        )
    elif stage2_evaluations:
        resume_from = 3
        logger.info(f"[RESUME] Resuming from Stage 3 for response {response_id}")
    elif stage1_responses:
        resume_from = 2
        logger.info(f"[RESUME] Resuming from Stage 2 for response {response_id}")
    else:
        resume_from = 1
        logger.info(f"[RESUME] Resuming from Stage 1 for response {response_id}")

    # Capture values for the generator closure
    captured_response_id = response_id
    captured_conv_id = conv_id
    user_id = user.id

    async def resume_generator():
        from ..stage_executor import (
            StageContext, sse_event, execute_stage1, execute_stage2,
            execute_stage3, finalize_response
        )

        # Initialize stage context
        ctx = StageContext(
            response_id=captured_response_id,
            user_query=user_query,
            log_prefix="[RESUME]",
            stage1_results=stage1_responses or [],
            stage2_results=stage2_evaluations or [],
            label_to_model=metadata.get("label_to_model", {}) if metadata else {},
            aggregate_rankings=metadata.get("aggregate_rankings", []) if metadata else [],
        )
        copilot_models = get_copilot_models()

        try:
            # Emit resume_start event
            yield sse_event('resume_start', resume_from_stage=resume_from, response_id=captured_response_id)

            # Stage 1
            if resume_from == 1:
                yield sse_event('stage1_start', models=copilot_models)
                result = await execute_stage1(ctx, with_progress=False)
                if not result.success:
                    yield sse_event('error', message=result.error_message, stage='stage1', response_id=captured_response_id)
                    return
                yield sse_event('stage1_complete', data=result.data, duration_ms=result.duration_ms)
            else:
                yield sse_event('stage1_skipped', data=ctx.stage1_results, reused=True)

            # Stage 2
            if resume_from <= 2:
                yield sse_event('stage2_start')
                result = await execute_stage2(ctx)
                if not result.success:
                    yield sse_event('error', message=result.error_message, stage='stage2',
                                   stage1_data=ctx.stage1_results, response_id=captured_response_id)
                    return
                yield sse_event('stage2_complete', data=result.data, duration_ms=result.duration_ms, metadata=ctx.metadata)
            else:
                yield sse_event('stage2_skipped', data=ctx.stage2_results, metadata=ctx.metadata, reused=True)

            # Stage 3
            yield sse_event('stage3_start')
            result = await execute_stage3(ctx)
            if not result.success:
                yield sse_event('error', message=result.error_message, stage='stage3', response_id=captured_response_id)
                return
            yield sse_event('stage3_complete', data=result.data, duration_ms=result.duration_ms)

            # Finalize
            finalize_response(ctx)
            yield sse_event('complete', total_duration_ms=ctx.total_duration_ms, resumed=True)

        except asyncio.CancelledError:
            logger.warning(f"[RESUME] Client disconnected for response {captured_response_id}")
            try:
                storage.update_response_status(captured_response_id, "failed")
                supabase_client = storage.get_supabase_client()
                supabase_client.table("assistant_responses").update({
                    "error_details": {
                        "error": "Client disconnected during resume",
                        "failed_stage": "unknown",
                        "disconnected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }
                }).eq("id", captured_response_id).execute()
            except Exception as cleanup_error:
                logger.warning(f"[RESUME] Failed to mark response as failed after disconnect: {cleanup_error}")
            raise

        except Exception as e:
            logger.exception(f"[RESUME] Error resuming response {captured_response_id}")
            try:
                storage.set_response_error(captured_response_id, str(e), "unknown")
            except Exception as cleanup_error:
                logger.warning(f"[RESUME] Failed to mark response as failed: {cleanup_error}")
            yield sse_event('error', message=str(e), response_id=captured_response_id)

    return StreamingResponse(
        resume_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        }
    )

