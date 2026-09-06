"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio

from . import storage
from .conversation_context import format_context_prompt
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_critiques,
    stage3_synthesize_final,
    generate_direct_response,
    is_trivial_prompt,
    provider_failure_message,
)

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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
    developer_mode: bool = False


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
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    history = conversation.get("messages", [])
    if not isinstance(history, list):
        history = []
    is_first_message = not history
    council_query, context_info = format_context_prompt(
        request.content,
        history,
    )

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        council_query,
        developer_mode=request.developer_mode,
    )
    metadata["conversation_context"] = context_info

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    history = conversation.get("messages", [])
    if not isinstance(history, list):
        history = []
    is_first_message = not history
    council_query, context_info = format_context_prompt(
        request.content,
        history,
    )

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            metadata: Dict[str, Any] = {
                "developer_mode": request.developer_mode,
                "review_skipped": False,
                "pipeline": "collaborative-critique",
                "conversation_context": context_info,
            }

            if is_trivial_prompt(request.content):
                metadata["review_skipped"] = True
                metadata["skip_reason"] = "trivial_prompt"
                stage1_results = []
                stage2_results = []
                yield f"data: {json.dumps({'type': 'stage2_skipped', 'metadata': metadata})}\n\n"
                yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
                stage3_result = await generate_direct_response(council_query)
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result, 'metadata': metadata})}\n\n"
            else:
                # Stage 1: Collect responses
                yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
                raw_stage1_results = await stage1_collect_responses(council_query)
                if not raw_stage1_results:
                    metadata["errors"] = [{
                        "stage": "stage1",
                        "message": provider_failure_message(),
                    }]
                    if title_task:
                        title_task.cancel()
                    yield f"data: {json.dumps({'type': 'error', 'message': provider_failure_message(), 'metadata': metadata})}\n\n"
                    return
                stage1_results = raw_stage1_results if request.developer_mode else []
                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

                # Stage 2: Collect critiques
                yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
                raw_stage2_results, label_to_model = await stage2_collect_critiques(
                    council_query,
                    raw_stage1_results,
                )
                if request.developer_mode:
                    metadata["label_to_model"] = label_to_model
                stage2_results = raw_stage2_results if request.developer_mode else []
                yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': metadata})}\n\n"

                # Stage 3: Synthesize final answer
                yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
                stage3_result = await stage3_synthesize_final(
                    council_query,
                    raw_stage1_results,
                    raw_stage2_results,
                )
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result, 'metadata': metadata})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
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
