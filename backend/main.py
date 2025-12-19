"""FastAPI backend for Eternal Copilot."""

import logging
import time
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio

# Configure logging for the backend module to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from . import storage
from .auth import AuthenticatedUser, get_current_user
from .config import WORKOS_API_KEY, WORKOS_CLIENT_ID, ALLOWED_ORIGINS
from .copilot import (
    run_full_copilot,
    generate_conversation_title,
    stage1_collect_responses,
    stage1_collect_responses_with_progress,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    improve_user_prompt,
    get_copilot_models,
)
from .search import (
    generate_scoped_search_key,
    is_typesense_configured,
)
from .config import (
    TYPESENSE_HOST,
    TYPESENSE_API_KEY,
    TYPESENSE_SEARCH_ONLY_KEY,
)

logger = logging.getLogger(__name__)


def _check_required_configuration():
    """
    Check that all required services are configured on startup.
    Raises an exception if critical configuration is missing.
    """
    missing_vars = []

    # Check WorkOS configuration (required for authentication)
    if not WORKOS_API_KEY:
        missing_vars.append("WORKOS_API_KEY")
    if not WORKOS_CLIENT_ID:
        missing_vars.append("WORKOS_CLIENT_ID")

    # Check Typesense configuration (required for search)
    if not TYPESENSE_HOST:
        missing_vars.append("TYPESENSE_HOST")
    if not TYPESENSE_API_KEY:
        missing_vars.append("TYPESENSE_API_KEY")
    if not TYPESENSE_SEARCH_ONLY_KEY:
        missing_vars.append("TYPESENSE_SEARCH_ONLY_KEY")

    if missing_vars:
        error_message = (
            "\n"
            "=" * 60 + "\n"
            "❌ CONFIGURATION ERROR: Required environment variables missing\n"
            "=" * 60 + "\n"
            f"\nMissing variables:\n"
        )
        for var in missing_vars:
            error_message += f"  • {var}\n"

        error_message += (
            "\n"
            "How to fix:\n"
            "  1. Copy the appropriate .env file for your environment:\n"
            "     - Development: .env.development\n"
            "     - Staging: .env.staging\n"
            "     - Production: .env.production\n"
            "\n"
            "  2. Ensure all required variables are set:\n"
            "\n"
            "     WorkOS Authentication:\n"
            "       WORKOS_API_KEY=sk_test_...\n"
            "       WORKOS_CLIENT_ID=client_...\n"
            "\n"
            "     Typesense Cloud (https://cloud.typesense.org/):\n"
            "       TYPESENSE_HOST=xxx.a1.typesense.net\n"
            "       TYPESENSE_API_KEY=your-admin-api-key\n"
            "       TYPESENSE_SEARCH_ONLY_KEY=your-search-only-key\n"
            "\n"
            "  3. Restart the application after updating environment variables.\n"
            "\n"
            "=" * 60 + "\n"
        )

        logger.critical(error_message)
        raise RuntimeError(error_message)


# Validate required configuration on startup
_check_required_configuration()

app = FastAPI(title="Eternal Copilot API")

# Enable CORS - uses ALLOWED_ORIGINS from config (defaults to localhost for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    original_query: str | None = None  # Original user-typed query (before improvement)
    # For smart retry: skip stages that already completed successfully
    stage1_data: list | None = None  # Completed Stage 1 responses to reuse
    stage2_data: list | None = None  # Completed Stage 2 rankings to reuse
    stage2_metadata: dict | None = None  # label_to_model and aggregate_rankings from Stage 2


class ImprovePromptRequest(BaseModel):
    """Request to improve a prompt."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class PaginatedConversations(BaseModel):
    """Paginated list of conversations."""
    conversations: List[ConversationMetadata]
    has_more: bool


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Eternal Copilot API"}


@app.get("/api/search/key")
async def get_search_key(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get a scoped Typesense API key for the authenticated user.

    The returned key has the user_id filter embedded at the Typesense level,
    ensuring the user can only search their own data. The key expires after 1 hour.

    Returns:
        JSON with search_key, typesense_host, and typesense_port for client configuration.
    """
    if not is_typesense_configured():
        raise HTTPException(
            status_code=503,
            detail="Search is not configured. Contact your administrator."
        )

    try:
        from .config import TYPESENSE_HOST, TYPESENSE_PORT, TYPESENSE_PROTOCOL

        scoped_key = generate_scoped_search_key(user.id)
        return {
            "search_key": scoped_key,
            "typesense_host": TYPESENSE_HOST,
            "typesense_port": TYPESENSE_PORT,
            "typesense_protocol": TYPESENSE_PROTOCOL,
        }
    except Exception as e:
        logger.error(f"Failed to generate search key: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate search key"
        )


@app.post("/api/improve-prompt")
async def improve_prompt(
    request: ImprovePromptRequest,
    user: AuthenticatedUser = Depends(get_current_user)  # noqa: ARG001
):
    """Improve a user's prompt using an LLM."""
    improved = await improve_user_prompt(request.content)
    return {"improved_prompt": improved}


@app.get("/api/conversations", response_model=PaginatedConversations)
async def list_conversations(
    limit: int = 10,
    offset: int = 0,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    List conversations for the authenticated user with pagination.

    Args:
        limit: Maximum number of conversations to return (default: 10, max: 50)
        offset: Number of conversations to skip for pagination (default: 0)
    """
    # Enforce reasonable limits
    limit = min(max(1, limit), 50)
    offset = max(0, offset)

    return storage.list_conversations(user_id=user.id, limit=limit, offset=offset)


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(user: AuthenticatedUser = Depends(get_current_user)):
    """Create a new conversation for the authenticated user."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id, user_id=user.id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id, user_id=user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.get("/api/responses/{response_id}/partial-stages")
async def get_partial_stages(
    response_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Get partial stage data for a response (for smart retry).

    Returns the response status and any partial model responses that were
    saved before the deliberation failed. This enables smart retry to
    reuse successful model responses without making duplicate API calls.
    """
    result = storage.get_response_with_partial_stages(response_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Response not found")

    # Verify user owns this response by checking the conversation ownership
    response = result["response"]
    user_message_id = response.get("user_message_id")
    if not user_message_id:
        # Response has no linked message - should not happen in normal operation
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
    # Verify ownership using storage module's helper
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


@app.post("/api/responses/{response_id}/cancel")
async def cancel_response(
    response_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Cancel/abort a stale or orphaned deliberation.

    This endpoint marks an in-progress response as 'failed' so the user can retry.
    It's used when:
    - The browser was refreshed during a deliberation and the backend process died
    - A deliberation has been stuck for too long
    - The user wants to manually abort a stale deliberation

    Only in-progress responses can be cancelled. Already completed or failed
    responses cannot be cancelled.
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
            # Already failed, just return success
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


@app.post("/api/responses/{response_id}/resume")
async def resume_response(
    response_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Resume a failed deliberation from the last completed stage.

    This endpoint checks which stages have already been completed for a failed
    response and streams the remaining stages. It reuses persisted stage data
    to avoid duplicate API calls.

    Returns SSE stream with the remaining stages (similar to /message/stream).
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

    # Check if the response is in a failed state (only failed responses can be resumed)
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
        # All stages complete - this shouldn't happen for 'failed' status but handle it
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
        stage1_duration_ms = 0
        stage2_duration_ms = 0
        stage3_duration_ms = 0
        stage1_results = stage1_responses or []
        stage2_results = stage2_evaluations or []
        label_to_model = metadata.get("label_to_model", {}) if metadata else {}
        aggregate_rankings = metadata.get("aggregate_rankings", []) if metadata else []
        copilot_models = get_copilot_models()

        try:
            # Emit resume_start event with info about what's being resumed
            yield f"data: {json.dumps({'type': 'resume_start', 'resume_from_stage': resume_from, 'response_id': captured_response_id})}\n\n"

            # Mark response as resuming (reset from failed)
            storage.update_response_status(captured_response_id, f"stage{resume_from}_in_progress")

            # Stage 1: Run only if not already complete
            if resume_from == 1:
                yield f"data: {json.dumps({'type': 'stage1_start', 'models': copilot_models})}\n\n"
                stage1_start = time.time()

                # Use stage1_collect_responses (non-progress version for simplicity)
                from .copilot import stage1_collect_responses
                stage1_results = await stage1_collect_responses(user_query)
                stage1_duration_ms = int((time.time() - stage1_start) * 1000)
                logger.info(f"[RESUME] Stage 1 completed in {stage1_duration_ms/1000:.1f}s for response {captured_response_id}")

                if not stage1_results:
                    error_msg = "All models failed to respond. Please try again later."
                    storage.set_response_error(captured_response_id, error_msg, "stage1")
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'stage': 'stage1', 'response_id': captured_response_id})}\n\n"
                    return

                storage.update_response_stage1(captured_response_id, stage1_results, stage1_duration_ms)
                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results, 'duration_ms': stage1_duration_ms})}\n\n"
            else:
                # Emit stage1_skipped to let frontend know we're reusing existing data
                yield f"data: {json.dumps({'type': 'stage1_skipped', 'data': stage1_results, 'reused': True})}\n\n"

            # Stage 2: Run only if not already complete
            if resume_from <= 2:
                if resume_from == 2:
                    # Resuming from Stage 2 - need to run it
                    storage.update_response_status(captured_response_id, "stage2_in_progress")
                    yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
                    stage2_start = time.time()
                    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)
                    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
                    stage2_duration_ms = int((time.time() - stage2_start) * 1000)
                    logger.info(f"[RESUME] Stage 2 completed in {stage2_duration_ms/1000:.1f}s for response {captured_response_id}")

                    if not stage2_results:
                        error_msg = "All ranking models failed to respond. Please try again later."
                        storage.set_response_error(captured_response_id, error_msg, "stage2")
                        yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'stage': 'stage2', 'stage1_data': stage1_results, 'response_id': captured_response_id})}\n\n"
                        return

                    resume_metadata = {"label_to_model": label_to_model, "aggregate_rankings": aggregate_rankings}
                    storage.update_response_stage2(captured_response_id, stage2_results, stage2_duration_ms, resume_metadata)
                    yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'duration_ms': stage2_duration_ms, 'metadata': resume_metadata})}\n\n"
                elif resume_from == 1:
                    # We just ran Stage 1, now run Stage 2
                    storage.update_response_status(captured_response_id, "stage2_in_progress")
                    yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
                    stage2_start = time.time()
                    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)
                    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
                    stage2_duration_ms = int((time.time() - stage2_start) * 1000)
                    logger.info(f"[RESUME] Stage 2 completed in {stage2_duration_ms/1000:.1f}s for response {captured_response_id}")

                    if not stage2_results:
                        error_msg = "All ranking models failed to respond. Please try again later."
                        storage.set_response_error(captured_response_id, error_msg, "stage2")
                        yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'stage': 'stage2', 'stage1_data': stage1_results, 'response_id': captured_response_id})}\n\n"
                        return

                    resume_metadata = {"label_to_model": label_to_model, "aggregate_rankings": aggregate_rankings}
                    storage.update_response_stage2(captured_response_id, stage2_results, stage2_duration_ms, resume_metadata)
                    yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'duration_ms': stage2_duration_ms, 'metadata': resume_metadata})}\n\n"
            else:
                # Resuming from Stage 3 - emit stage2_skipped
                yield f"data: {json.dumps({'type': 'stage2_skipped', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}, 'reused': True})}\n\n"

            # Stage 3: Always run (this is the final step)
            storage.update_response_status(captured_response_id, "stage3_in_progress")
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_start = time.time()
            stage3_result = await stage3_synthesize_final(user_query, stage1_results, stage2_results)
            stage3_duration_ms = int((time.time() - stage3_start) * 1000)
            logger.info(f"[RESUME] Stage 3 completed in {stage3_duration_ms/1000:.1f}s for response {captured_response_id}")

            # Save Stage 3 results
            storage.update_response_stage3(captured_response_id, stage3_result, stage3_duration_ms)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result, 'duration_ms': stage3_duration_ms})}\n\n"

            # Mark response as complete and cleanup
            storage.update_response_status(captured_response_id, "complete")
            storage.cleanup_partial_stage_responses(captured_response_id)
            logger.info(f"[RESUME] Marked response {captured_response_id} as complete")

            # Send completion event
            total_duration_ms = stage1_duration_ms + stage2_duration_ms + stage3_duration_ms
            logger.info(
                f"[RESUME] Deliberation resumed and completed for response {captured_response_id}: "
                f"Stage1={stage1_duration_ms/1000:.1f}s, Stage2={stage2_duration_ms/1000:.1f}s, "
                f"Stage3={stage3_duration_ms/1000:.1f}s, Total={total_duration_ms/1000:.1f}s"
            )
            yield f"data: {json.dumps({'type': 'complete', 'total_duration_ms': total_duration_ms, 'resumed': True})}\n\n"

        except asyncio.CancelledError:
            logger.warning(f"[RESUME] Client disconnected for response {captured_response_id}")
            try:
                storage.update_response_status(captured_response_id, "failed")
                supabase.table("assistant_responses").update({
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
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'response_id': captured_response_id})}\n\n"

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


@app.post("/api/conversations/{conversation_id}/message")
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

    # Add user message
    storage.add_user_message(conversation_id, user_id=user.id, content=request.content)

    # Store the original/improved query for first message
    if is_first_message:
        if request.original_query:
            # User improved the prompt: original_query has the original, content has improved
            storage.update_conversation_queries(
                conversation_id,
                user_id=user.id,
                original_query=request.original_query,
                improved_query=request.content,
            )
        else:
            # No improvement: content is the original query
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

    # Add assistant message with all stages and timing
    storage.add_assistant_message(
        conversation_id,
        user_id=user.id,
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

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
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
    # IMPORTANT: Capture conversation_id explicitly to avoid closure issues
    captured_conversation_id = conversation_id

    logger.info(f"[STREAM] Starting stream for conversation_id={captured_conversation_id}, user_id={user_id}")

    async def event_generator():
        # Queue for model completion events during stage 1
        model_events = asyncio.Queue()
        logger.info(f"[STREAM] event_generator started for conversation_id={captured_conversation_id}")

        # Track timing for each stage
        stage1_duration_ms = 0
        stage2_duration_ms = 0
        stage3_duration_ms = 0

        async def on_model_complete(model: str, response_content, success: bool, elapsed_ms: int):
            """Callback when a model completes - adds event to queue AND persists to DB."""
            nonlocal response_id  # Will be set by the time Stage 1 starts
            elapsed_sec = elapsed_ms / 1000
            status = "succeeded" if success else "failed"
            logger.info(f"[STREAM] Model {model} {status} in {elapsed_sec:.1f}s for conversation {captured_conversation_id}")

            # Persist individual model response immediately (incremental persistence)
            # This enables smart retry at the model level if Stage 1 fails mid-way
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
                    logger.debug(f"[STREAM] Persisted model response for {model} to DB")
                except Exception as e:
                    # Log but don't fail - the event still goes to frontend
                    logger.warning(f"[STREAM] Failed to persist model response for {model}: {e}")

            event = {
                'type': 'model_response',
                'model': model,
                'success': success,
                'elapsed_ms': elapsed_ms,
                'response_content': response_content,
            }
            await model_events.put(event)
            logger.debug(f"[STREAM] Added model_response event to queue for {model}")

        # Initialize response_id before try block so it's accessible in except for cleanup
        response_id = None

        try:
            # Step 1: Save user message immediately (incremental persistence)
            user_message_id = storage.add_user_message(
                captured_conversation_id, user_id=user_id, content=request.content
            )
            logger.info(f"[STREAM] Saved user message {user_message_id} to conversation {captured_conversation_id}")

            # Store the original/improved query for first message
            if is_first_message:
                if request.original_query:
                    # User improved the prompt: original_query has the original, content has improved
                    storage.update_conversation_queries(
                        captured_conversation_id,
                        user_id=user_id,
                        original_query=request.original_query,
                        improved_query=request.content,
                    )
                    logger.info(f"[STREAM] Saved queries (with improvement) to conversation {captured_conversation_id}")
                else:
                    # No improvement: content is the original query
                    storage.update_conversation_queries(
                        captured_conversation_id, user_id=user_id, original_query=request.content
                    )
                    logger.info(f"[STREAM] Saved original query to conversation {captured_conversation_id}")

            # Step 2: Create assistant response placeholder for incremental updates
            # In the FK design, the response is linked to the user message via foreign key
            response_id = storage.create_response_placeholder(user_message_id)
            logger.info(f"[STREAM] Created response placeholder {response_id} for user message {user_message_id}")

            # Start title generation in parallel with its own queue for immediate emission
            title_task = None
            title_queue: asyncio.Queue = asyncio.Queue()
            title_emitted = False

            async def title_generation_wrapper():
                """Wrapper that generates title and puts result in queue for immediate emission."""
                try:
                    logger.info(f"[STREAM] Starting title generation for conversation {captured_conversation_id}")
                    title = await generate_conversation_title(request.content)
                    logger.info(f"[STREAM] Title generation completed: '{title}' for conversation {captured_conversation_id}")
                    await title_queue.put(title)
                    return title
                except Exception as e:
                    logger.error(f"[STREAM] Title generation error: {e}")
                    await title_queue.put(None)
                    return None

            if is_first_message:
                logger.info(f"[STREAM] is_first_message=True, starting title task for conversation {captured_conversation_id}")
                title_task = asyncio.create_task(title_generation_wrapper())
            else:
                logger.info(f"[STREAM] is_first_message=False, skipping title generation for conversation {captured_conversation_id}")

            # Helper to check and emit title if ready (non-blocking)
            async def check_and_emit_title():
                nonlocal title_emitted
                if title_emitted or title_task is None:
                    return None
                try:
                    title = title_queue.get_nowait()
                    if title:
                        storage.update_conversation_title(captured_conversation_id, user_id=user_id, title=title)
                        logger.info(f"[STREAM] Saved title '{title}' to conversation {captured_conversation_id}")
                        title_emitted = True
                        return f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"
                except asyncio.QueueEmpty:
                    pass
                return None

            # Stage 1: Collect responses (or reuse from retry)
            if request.stage1_data:
                # Smart retry: reuse Stage 1 results from previous failed attempt
                stage1_results = request.stage1_data
                stage1_duration_ms = 0  # No time spent, reusing cached data
                logger.info(f"[STREAM] Reusing {len(stage1_results)} Stage 1 responses from retry for conversation {captured_conversation_id}")

                # Still save to storage for consistency (in case Stage 2/3 fail again)
                storage.update_response_stage1(
                    response_id, stage1_results, stage1_duration_ms
                )
                logger.info(f"[STREAM] Saved reused stage1 results for response {response_id}")

                yield f"data: {json.dumps({'type': 'stage1_skipped', 'data': stage1_results, 'reused': True})}\n\n"
            else:
                # Normal flow: collect responses from all models
                logger.info(f"[STREAM] Starting Stage 1 with {len(copilot_models)} models for conversation {captured_conversation_id}")

                # Update response status to stage1_in_progress (incremental persistence)
                storage.update_response_status(response_id, "stage1_in_progress")

                yield f"data: {json.dumps({'type': 'stage1_start', 'models': copilot_models})}\n\n"

                stage1_start = time.time()

                # Start stage1 with progress tracking
                logger.info(f"[STREAM] Launching parallel model queries for conversation {captured_conversation_id}")
                stage1_task = asyncio.create_task(
                    stage1_collect_responses_with_progress(request.content, on_model_complete)
                )

                # Emit model completion events as they arrive, checking for title in between
                models_remaining = len(copilot_models)
                logger.info(f"[STREAM] Waiting for {models_remaining} model responses...")
                while models_remaining > 0:
                    event = await model_events.get()
                    logger.info(f"[STREAM] Emitting model_response event for {event.get('model')} ({models_remaining - 1} remaining)")
                    yield f"data: {json.dumps(event)}\n\n"
                    models_remaining -= 1
                    # Check if title is ready while waiting for model responses
                    title_event = await check_and_emit_title()
                    if title_event:
                        yield title_event

                # Wait for stage1 to complete and get results
                stage1_results = await stage1_task
                stage1_duration_ms = int((time.time() - stage1_start) * 1000)
                stage1_duration_sec = stage1_duration_ms / 1000
                successful_models = len(stage1_results)
                logger.info(f"[STREAM] Stage 1 completed in {stage1_duration_sec:.1f}s - {successful_models}/{len(copilot_models)} models responded for conversation {captured_conversation_id}")

                # Check for title after stage1 completes
                title_event = await check_and_emit_title()
                if title_event:
                    yield title_event

                # Step 3: Save Stage 1 results immediately (incremental persistence)
                storage.update_response_stage1(
                    response_id, stage1_results, stage1_duration_ms
                )
                # Update response status to stage1_complete
                storage.update_response_status(response_id, "stage1_complete")
                logger.info(f"[STREAM] Saved stage1 results for response {response_id} (user message {user_message_id})")

                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results, 'duration_ms': stage1_duration_ms})}\n\n"

            # Check if we have any successful Stage 1 responses
            # If all models failed, we cannot proceed to Stage 2 ranking
            if not stage1_results:
                error_msg = "All models failed to respond. Please try again later."
                logger.error(f"[STREAM] Stage 1 failed - no model responses received for conversation {captured_conversation_id}")

                # Cancel title_task if it exists and is still running
                if title_task is not None and not title_task.done():
                    title_task.cancel()
                    try:
                        await title_task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass

                # Mark response as failed with error details (preserves partial data for smart retry)
                if response_id is not None:
                    storage.set_response_error(response_id, error_msg, "stage1")
                    logger.info(f"[STREAM] Marked response {response_id} as failed (stage1)")
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'conversation_id': captured_conversation_id, 'stage': 'stage1', 'response_id': response_id})}\n\n"
                return

            # Stage 2: Collect rankings (or reuse from retry)
            if request.stage2_data and request.stage2_metadata:
                # Smart retry: reuse Stage 2 results from previous failed attempt
                stage2_results = request.stage2_data
                label_to_model = request.stage2_metadata.get("label_to_model", {})
                aggregate_rankings = request.stage2_metadata.get("aggregate_rankings", [])
                metadata = request.stage2_metadata
                stage2_duration_ms = 0  # No time spent, reusing cached data
                logger.info(f"[STREAM] Reusing Stage 2 rankings from retry for conversation {captured_conversation_id}")

                # Still save to storage for consistency (in case Stage 3 fails again)
                storage.update_response_stage2(
                    response_id, stage2_results, stage2_duration_ms, metadata
                )
                logger.info(f"[STREAM] Saved reused stage2 results for response {response_id}")

                yield f"data: {json.dumps({'type': 'stage2_skipped', 'data': stage2_results, 'metadata': metadata, 'reused': True})}\n\n"
            else:
                # Normal flow: collect rankings from all models
                # Update response status to stage2_in_progress (incremental persistence)
                storage.update_response_status(response_id, "stage2_in_progress")

                yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
                stage2_start = time.time()
                stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
                aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
                stage2_duration_ms = int((time.time() - stage2_start) * 1000)
                stage2_duration_sec = stage2_duration_ms / 1000
                successful_rankings = len(stage2_results)
                logger.info(f"[STREAM] Stage 2 completed in {stage2_duration_sec:.1f}s - {successful_rankings}/{len(copilot_models)} rankings received for conversation {captured_conversation_id}")

                # Check for title after stage2 completes
                title_event = await check_and_emit_title()
                if title_event:
                    yield title_event

                # Step 4: Save Stage 2 results immediately (incremental persistence)
                metadata = {
                    "label_to_model": label_to_model,
                    "aggregate_rankings": aggregate_rankings,
                }
                storage.update_response_stage2(
                    response_id, stage2_results, stage2_duration_ms, metadata
                )
                # Update response status to stage2_complete
                storage.update_response_status(response_id, "stage2_complete")
                logger.info(f"[STREAM] Saved stage2 results for response {response_id} (user message {user_message_id})")

                yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'duration_ms': stage2_duration_ms, 'metadata': metadata})}\n\n"

            # Check if we have any successful Stage 2 rankings
            # If all ranking models failed, we cannot proceed to Stage 3 synthesis
            if not stage2_results:
                error_msg = "All ranking models failed to respond. Please try again later."
                logger.error(f"[STREAM] Stage 2 failed - no rankings received for conversation {captured_conversation_id}")

                # Cancel title_task if it exists and is still running
                if title_task is not None and not title_task.done():
                    title_task.cancel()
                    try:
                        await title_task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass

                # Mark response as failed with error details (preserves partial data for smart retry)
                if response_id is not None:
                    storage.set_response_error(response_id, error_msg, "stage2")
                    logger.info(f"[STREAM] Marked response {response_id} as failed (stage2)")
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'conversation_id': captured_conversation_id, 'stage': 'stage2', 'stage1_data': stage1_results, 'response_id': response_id})}\n\n"
                return

            # Stage 3: Synthesize final answer (always run - this is where we left off on retry)
            # Update response status to stage3_in_progress (incremental persistence)
            storage.update_response_status(response_id, "stage3_in_progress")

            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_start = time.time()
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            stage3_duration_ms = int((time.time() - stage3_start) * 1000)
            stage3_duration_sec = stage3_duration_ms / 1000
            logger.info(f"[STREAM] Stage 3 completed in {stage3_duration_sec:.1f}s for conversation {captured_conversation_id}")

            # Check for title after stage3 completes
            title_event = await check_and_emit_title()
            if title_event:
                yield title_event

            # Step 5: Save Stage 3 results immediately (incremental persistence)
            storage.update_response_stage3(
                response_id, stage3_result, stage3_duration_ms
            )
            logger.info(f"[STREAM] Saved stage3 results for response {response_id} (user message {user_message_id})")

            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result, 'duration_ms': stage3_duration_ms})}\n\n"

            # Final check: ensure title is emitted before completion if still pending
            if title_task and not title_emitted:
                try:
                    title = await asyncio.wait_for(title_task, timeout=5.0)
                    if title and not title_emitted:
                        storage.update_conversation_title(captured_conversation_id, user_id=user_id, title=title)
                        logger.info(f"[STREAM] Saved title '{title}' to conversation {captured_conversation_id}")
                        yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"
                except asyncio.TimeoutError:
                    logger.warning(f"[STREAM] Title generation timed out for conversation {captured_conversation_id}")
                except Exception as e:
                    logger.error(f"[STREAM] Title generation error: {e}")

            # Mark response as complete and cleanup partial stage responses
            storage.update_response_status(response_id, "complete")
            storage.cleanup_partial_stage_responses(response_id)
            logger.info(f"[STREAM] Marked response {response_id} as complete and cleaned up partial stage data")

            # Send completion event with total timing
            total_duration_ms = stage1_duration_ms + stage2_duration_ms + stage3_duration_ms
            total_duration_sec = total_duration_ms / 1000
            logger.info(
                f"[STREAM] Deliberation completed for conversation {captured_conversation_id}: "
                f"Stage1={stage1_duration_ms/1000:.1f}s, Stage2={stage2_duration_ms/1000:.1f}s, "
                f"Stage3={stage3_duration_ms/1000:.1f}s, Total={total_duration_sec:.1f}s"
            )
            yield f"data: {json.dumps({'type': 'complete', 'total_duration_ms': total_duration_ms})}\n\n"

        except asyncio.CancelledError:
            # Client disconnected mid-stream (e.g., browser refresh, tab close)
            # Mark the response as failed so the user can retry when they return
            logger.warning(
                f"[STREAM] Client disconnected for conversation {captured_conversation_id}, "
                f"response_id={response_id}"
            )

            # Cancel title_task if it exists and is still running
            if title_task is not None and not title_task.done():
                title_task.cancel()
                try:
                    await title_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

            # Mark response as failed due to client disconnection
            if response_id is not None:
                try:
                    storage.update_response_status(response_id, "failed")
                    # Also set error details to indicate client disconnection
                    supabase = storage.get_supabase_client()
                    supabase.table("assistant_responses").update({
                        "error_details": {
                            "error": "Client disconnected during deliberation",
                            "failed_stage": "unknown",
                            "disconnected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        }
                    }).eq("id", response_id).execute()
                    logger.info(f"[STREAM] Marked response {response_id} as failed (client disconnected)")
                except Exception as cleanup_error:
                    logger.warning(f"[STREAM] Failed to mark response as failed after disconnect: {cleanup_error}")

            # Re-raise to properly close the generator
            raise

        except Exception as e:
            # Cancel title_task if it exists and is still running
            if title_task is not None and not title_task.done():
                title_task.cancel()
                try:
                    await title_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

            # Mark response as failed with error details (preserves partial data for smart retry)
            if response_id is not None:
                try:
                    storage.set_response_error(response_id, str(e), "unknown")
                    logger.info(f"[STREAM] Marked response {response_id} as failed (exception)")
                except Exception as cleanup_error:
                    logger.warning(f"[STREAM] Failed to mark response as failed: {cleanup_error}")

            # Send error event with conversation_id and response_id for frontend smart retry
            logger.exception("Error in streaming endpoint")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'conversation_id': captured_conversation_id, 'response_id': response_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Content-Type": "text/event-stream; charset=utf-8",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
