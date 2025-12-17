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


class ImprovePromptRequest(BaseModel):
    """Request to improve a prompt."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


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


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(user: AuthenticatedUser = Depends(get_current_user)):
    """List all conversations for the authenticated user (metadata only)."""
    return storage.list_conversations(user_id=user.id)


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
            """Callback when a model completes - adds event to queue."""
            event = {
                'type': 'model_response',
                'model': model,
                'success': success,
                'elapsed_ms': elapsed_ms,
                'response_content': response_content,
            }
            await model_events.put(event)

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

            # Stage 1: Collect responses with individual model progress
            yield f"data: {json.dumps({'type': 'stage1_start', 'models': copilot_models})}\n\n"

            stage1_start = time.time()

            # Start stage1 with progress tracking
            stage1_task = asyncio.create_task(
                stage1_collect_responses_with_progress(request.content, on_model_complete)
            )

            # Emit model completion events as they arrive, checking for title in between
            models_remaining = len(copilot_models)
            while models_remaining > 0:
                event = await model_events.get()
                yield f"data: {json.dumps(event)}\n\n"
                models_remaining -= 1
                # Check if title is ready while waiting for model responses
                title_event = await check_and_emit_title()
                if title_event:
                    yield title_event

            # Wait for stage1 to complete and get results
            stage1_results = await stage1_task
            stage1_duration_ms = int((time.time() - stage1_start) * 1000)

            # Check for title after stage1 completes
            title_event = await check_and_emit_title()
            if title_event:
                yield title_event

            # Step 3: Save Stage 1 results immediately (incremental persistence)
            storage.update_response_stage1(
                response_id, stage1_results, stage1_duration_ms
            )
            logger.info(f"[STREAM] Saved stage1 results for response {response_id} (user message {user_message_id})")

            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results, 'duration_ms': stage1_duration_ms})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_start = time.time()
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            stage2_duration_ms = int((time.time() - stage2_start) * 1000)

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
            logger.info(f"[STREAM] Saved stage2 results for response {response_id} (user message {user_message_id})")

            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'duration_ms': stage2_duration_ms, 'metadata': metadata})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_start = time.time()
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            stage3_duration_ms = int((time.time() - stage3_start) * 1000)

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

            # Send completion event with total timing
            total_duration_ms = stage1_duration_ms + stage2_duration_ms + stage3_duration_ms
            yield f"data: {json.dumps({'type': 'complete', 'total_duration_ms': total_duration_ms})}\n\n"

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

            # Clean up incomplete assistant response placeholder to prevent
            # "Chairman: Unknown" from showing in the UI
            if response_id is not None:
                deleted = storage.delete_response_placeholder(response_id)
                if deleted:
                    logger.info(f"[STREAM] Deleted incomplete response placeholder {response_id}")
                else:
                    logger.warning(f"[STREAM] Failed to delete response placeholder {response_id}")

            # Send error event with conversation_id for frontend cleanup
            logger.exception("Error in streaming endpoint")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'conversation_id': captured_conversation_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
