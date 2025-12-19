"""Streaming deliberation logic for message/stream endpoint."""

import logging
import time
import json
import asyncio
from typing import List, AsyncIterator

from .. import storage
from ..copilot import (
    generate_conversation_title,
    stage1_collect_responses_with_progress,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
)
from .models import SendMessageRequest

logger = logging.getLogger(__name__)


async def stream_deliberation(
    conversation_id: str,
    user_id: str,
    request: SendMessageRequest,
    is_first_message: bool,
    copilot_models: List[str],
) -> AsyncIterator[str]:
    """
    Stream the 3-stage deliberation process as SSE events.
    
    This generator yields SSE events as each stage and model completes.
    It handles incremental persistence, title generation, and error recovery.
    """
    # Queue for model completion events during stage 1
    model_events: asyncio.Queue = asyncio.Queue()
    logger.info(f"[STREAM] event_generator started for conversation_id={conversation_id}")

    # Track timing for each stage
    stage1_duration_ms = 0
    stage2_duration_ms = 0
    stage3_duration_ms = 0

    # Initialize response_id before try block for cleanup access
    response_id = None
    title_task = None
    title_emitted = False

    async def on_model_complete(model: str, response_content, success: bool, elapsed_ms: int):
        """Callback when a model completes - adds event to queue AND persists to DB."""
        nonlocal response_id
        elapsed_sec = elapsed_ms / 1000
        status = "succeeded" if success else "failed"
        logger.info(f"[STREAM] Model {model} {status} in {elapsed_sec:.1f}s for conversation {conversation_id}")

        # Persist individual model response immediately
        if response_id is not None:
            try:
                storage.save_model_response(
                    assistant_response_id=response_id,
                    stage=1,
                    model_name=model,
                    response_content={"content": response_content} if response_content else None,
                    elapsed_ms=elapsed_ms,
                    success=success,
                    error_message=None if success else "Model failed to respond",
                )
            except Exception as e:
                logger.warning(f"[STREAM] Failed to persist model response for {model}: {e}")

        event = {
            'type': 'model_response',
            'model': model,
            'success': success,
            'elapsed_ms': elapsed_ms,
            'response_content': response_content,
        }
        await model_events.put(event)

    try:
        # Step 1: Save user message immediately
        user_message_id = storage.add_user_message(
            conversation_id, user_id=user_id, content=request.content
        )
        logger.info(f"[STREAM] Saved user message {user_message_id} to conversation {conversation_id}")

        # Store the original/improved query for first message
        if is_first_message:
            if request.original_query:
                storage.update_conversation_queries(
                    conversation_id,
                    user_id=user_id,
                    original_query=request.original_query,
                    improved_query=request.content,
                )
            else:
                storage.update_conversation_queries(
                    conversation_id, user_id=user_id, original_query=request.content
                )

        # Step 2: Create assistant response placeholder
        response_id = storage.create_response_placeholder(user_message_id)
        logger.info(f"[STREAM] Created response placeholder {response_id}")

        # Start title generation in parallel
        title_queue: asyncio.Queue = asyncio.Queue()

        async def title_generation_wrapper():
            try:
                title = await generate_conversation_title(request.content)
                await title_queue.put(title)
                return title
            except Exception as e:
                logger.error(f"[STREAM] Title generation error: {e}")
                await title_queue.put(None)
                return None

        if is_first_message:
            title_task = asyncio.create_task(title_generation_wrapper())

        async def check_and_emit_title():
            nonlocal title_emitted
            if title_emitted or title_task is None:
                return None
            try:
                title = title_queue.get_nowait()
                if title:
                    storage.update_conversation_title(conversation_id, user_id=user_id, title=title)
                    title_emitted = True
                    return f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"
            except asyncio.QueueEmpty:
                pass
            return None

        # Stage 1: Collect responses (or reuse from retry)
        if request.stage1_data:
            stage1_results = request.stage1_data
            stage1_duration_ms = 0
            storage.update_response_stage1(response_id, stage1_results, stage1_duration_ms)
            yield f"data: {json.dumps({'type': 'stage1_skipped', 'data': stage1_results, 'reused': True})}\n\n"
        else:
            storage.update_response_status(response_id, "stage1_in_progress")
            yield f"data: {json.dumps({'type': 'stage1_start', 'models': copilot_models})}\n\n"

            stage1_start = time.time()
            stage1_task = asyncio.create_task(
                stage1_collect_responses_with_progress(request.content, on_model_complete)
            )

            # Emit model completion events as they arrive
            models_remaining = len(copilot_models)
            while models_remaining > 0:
                event = await model_events.get()
                yield f"data: {json.dumps(event)}\n\n"
                models_remaining -= 1
                title_event = await check_and_emit_title()
                if title_event:
                    yield title_event

            stage1_results = await stage1_task
            stage1_duration_ms = int((time.time() - stage1_start) * 1000)

            title_event = await check_and_emit_title()
            if title_event:
                yield title_event

            storage.update_response_stage1(response_id, stage1_results, stage1_duration_ms)
            storage.update_response_status(response_id, "stage1_complete")
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results, 'duration_ms': stage1_duration_ms})}\n\n"

        # Check if we have any successful Stage 1 responses
        if not stage1_results:
            error_msg = "All models failed to respond. Please try again later."
            if title_task is not None and not title_task.done():
                title_task.cancel()
            if response_id is not None:
                storage.set_response_error(response_id, error_msg, "stage1")
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'conversation_id': conversation_id, 'stage': 'stage1', 'response_id': response_id})}\n\n"
            return

        # Stage 2: Collect rankings (or reuse from retry)
        if request.stage2_data and request.stage2_metadata:
            stage2_results = request.stage2_data
            label_to_model = request.stage2_metadata.get("label_to_model", {})
            aggregate_rankings = request.stage2_metadata.get("aggregate_rankings", [])
            metadata = request.stage2_metadata
            stage2_duration_ms = 0
            storage.update_response_stage2(response_id, stage2_results, stage2_duration_ms, metadata)
            yield f"data: {json.dumps({'type': 'stage2_skipped', 'data': stage2_results, 'metadata': metadata, 'reused': True})}\n\n"
        else:
            storage.update_response_status(response_id, "stage2_in_progress")
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"

            stage2_start = time.time()
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            stage2_duration_ms = int((time.time() - stage2_start) * 1000)

            title_event = await check_and_emit_title()
            if title_event:
                yield title_event

            metadata = {
                "label_to_model": label_to_model,
                "aggregate_rankings": aggregate_rankings,
            }
            storage.update_response_stage2(response_id, stage2_results, stage2_duration_ms, metadata)
            storage.update_response_status(response_id, "stage2_complete")
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'duration_ms': stage2_duration_ms, 'metadata': metadata})}\n\n"

        # Check if we have any successful Stage 2 rankings
        if not stage2_results:
            error_msg = "All ranking models failed to respond. Please try again later."
            if title_task is not None and not title_task.done():
                title_task.cancel()
            if response_id is not None:
                storage.set_response_error(response_id, error_msg, "stage2")
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'conversation_id': conversation_id, 'stage': 'stage2', 'stage1_data': stage1_results, 'response_id': response_id})}\n\n"
            return

        # Stage 3: Synthesize final answer
        storage.update_response_status(response_id, "stage3_in_progress")
        yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"

        stage3_start = time.time()
        stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
        stage3_duration_ms = int((time.time() - stage3_start) * 1000)

        title_event = await check_and_emit_title()
        if title_event:
            yield title_event

        storage.update_response_stage3(response_id, stage3_result, stage3_duration_ms)
        yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result, 'duration_ms': stage3_duration_ms})}\n\n"

        # Final check: ensure title is emitted before completion
        if title_task and not title_emitted:
            try:
                title = await asyncio.wait_for(title_task, timeout=5.0)
                if title and not title_emitted:
                    storage.update_conversation_title(conversation_id, user_id=user_id, title=title)
                    yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"[STREAM] Title generation issue: {e}")

        # Mark response as complete
        storage.update_response_status(response_id, "complete")
        storage.cleanup_partial_stage_responses(response_id)

        total_duration_ms = stage1_duration_ms + stage2_duration_ms + stage3_duration_ms
        logger.info(f"[STREAM] Deliberation completed: Total={total_duration_ms/1000:.1f}s")
        yield f"data: {json.dumps({'type': 'complete', 'total_duration_ms': total_duration_ms})}\n\n"

    except asyncio.CancelledError:
        logger.warning(f"[STREAM] Client disconnected for conversation {conversation_id}")
        if title_task is not None and not title_task.done():
            title_task.cancel()
        if response_id is not None:
            try:
                storage.update_response_status(response_id, "failed")
                supabase = storage.get_supabase_client()
                supabase.table("assistant_responses").update({
                    "error_details": {
                        "error": "Client disconnected during deliberation",
                        "failed_stage": "unknown",
                        "disconnected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }
                }).eq("id", response_id).execute()
            except Exception as cleanup_error:
                logger.warning(f"[STREAM] Failed to mark response as failed: {cleanup_error}")
        raise

    except Exception as e:
        if title_task is not None and not title_task.done():
            title_task.cancel()
        if response_id is not None:
            try:
                storage.set_response_error(response_id, str(e), "unknown")
            except Exception as cleanup_error:
                logger.warning(f"[STREAM] Failed to mark response as failed: {cleanup_error}")
        logger.exception("Error in streaming endpoint")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'conversation_id': conversation_id, 'response_id': response_id})}\n\n"

