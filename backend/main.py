"""FastAPI backend for LLM Council."""

import uuid
import json
import asyncio
from contextlib import asynccontextmanager
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import storage
from .rag import rag_engine
from .council import (
    run_full_council, 
    generate_conversation_title, 
    stage1_collect_responses, 
    stage1_collect_responses, 
    stage3_synthesize_final, 
    stage3_synthesize_final_stream
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await storage.initialize_storage()
    yield
    # Shutdown
    pass


app = FastAPI(title="LLM Council API", lifespan=lifespan)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    return await storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest = None):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = await storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = await storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/upload")
async def upload_file(conversation_id: str, file: UploadFile = File(...)):
    """Upload a file for RAG context."""
    # Check if conversation exists
    conversation = await storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    try:
        content = await file.read()
        result = rag_engine.process_file(conversation_id, content, file.filename)
        if "error" in result:
             raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/conversations/{conversation_id}/files/{filename}")
async def delete_file(conversation_id: str, filename: str):
    """Remove a file from RAG context."""
    # Check if conversation exists
    conversation = await storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    try:
        success = rag_engine.remove_file(conversation_id, filename)
        if not success:
             raise HTTPException(status_code=404, detail="File not found in context")
        return {"status": "success", "filename": filename}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = await storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Get history for context (before adding new message)
    history = await storage.get_chat_history(conversation_id)

    # Add user message
    await storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        await storage.update_conversation_title(conversation_id, title)

    # RAG Retrieval
    docs = rag_engine.search(conversation_id, request.content, k=3)
    context = ""
    if docs:
        context = "\n\n".join([f"Source: {d['source']}\nContent: {d['text']}" for d in docs])

    # Run the council process
    stage1_results, stage3_result = await run_full_council(
        request.content,
        history,
        context
    )

    # Add assistant message with results
    await storage.add_assistant_message(
        conversation_id,
        stage1_results,
        [], # No stage 2
        stage3_result,
        {}  # No metadata
    )

    # Return the complete response
    return {
        "stage1": stage1_results,
        "stage2": [], 
        "stage3": stage3_result,
        "metadata": {},
        "context": docs  # Return context for UI debugging/citations if needed
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = await storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Get history for context (before adding new message)
            history = await storage.get_chat_history(conversation_id)

            # Add user message
            await storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # RAG Retrieval
            docs = rag_engine.search(conversation_id, request.content, k=3)
            context = ""
            if docs:
                context = "\n\n".join([f"Source: {d['source']}\nContent: {d['text']}" for d in docs])
                # Send context event for UI
                yield f"data: {json.dumps({'type': 'rag_context', 'data': docs})}\n\n"

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content, history, context)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"


            # Stage 3: Synthesize final answer (with streaming)
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            
            full_response = ""
            async for chunk in stage3_synthesize_final_stream(request.content, stage1_results, history, context):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'stage3_chunk', 'chunk': chunk})}\n\n"
            
            stage3_result = {
                "model": "chairman", # Should be CHAIRMAN_MODEL constant, but handled by logic
                "response": full_response
            }
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                # Give it a timeout so it doesn't block forever if stuck
                try:
                    title = await asyncio.wait_for(title_task, timeout=5.0)
                    await storage.update_conversation_title(conversation_id, title)
                    yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"
                except Exception as e:
                    print(f"Title generation failed or timed out: {e}")

            # Save complete assistant message
            await storage.add_assistant_message(
                conversation_id,
                stage1_results,
                [], # No stage 2
                stage3_result,
                {} # No metadata
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            print(f"Error in stream: {e}")
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
