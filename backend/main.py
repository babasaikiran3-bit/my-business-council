"""FastAPI backend for Eternal Copilot."""

import logging
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

logger = logging.getLogger(__name__)

app = FastAPI(title="Eternal Copilot API")

# Check WorkOS configuration on startup
if not WORKOS_API_KEY or not WORKOS_CLIENT_ID:
    logger.critical(
        "CRITICAL: WorkOS credentials not configured. "
        "Set WORKOS_API_KEY and WORKOS_CLIENT_ID environment variables. "
        "All authenticated endpoints will return 500 errors until configured."
    )
    print(
        "\n⚠️  WARNING: WorkOS authentication is NOT configured!\n"
        "   Set WORKOS_API_KEY and WORKOS_CLIENT_ID in your .env file.\n"
        "   All API endpoints requiring authentication will return 500 errors.\n"
    )

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

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, user_id=user.id, title=title)

    # Run the 3-stage copilot process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_copilot(
        request.content
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        user_id=user.id,
        stage1=stage1_results,
        stage2=stage2_results,
        stage3=stage3_result
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

    # Capture user_id for use in the generator closure
    user_id = user.id

    async def event_generator():
        # Queue for model completion events during stage 1
        model_events = asyncio.Queue()

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

        try:
            # Add user message
            storage.add_user_message(conversation_id, user_id=user_id, content=request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses with individual model progress
            yield f"data: {json.dumps({'type': 'stage1_start', 'models': copilot_models})}\n\n"

            # Start stage1 with progress tracking
            stage1_task = asyncio.create_task(
                stage1_collect_responses_with_progress(request.content, on_model_complete)
            )

            # Emit model completion events as they arrive
            models_remaining = len(copilot_models)
            while models_remaining > 0:
                event = await model_events.get()
                yield f"data: {json.dumps(event)}\n\n"
                models_remaining -= 1

            # Wait for stage1 to complete and get results
            stage1_results = await stage1_task
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, user_id=user_id, title=title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                user_id=user_id,
                stage1=stage1_results,
                stage2=stage2_results,
                stage3=stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

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
