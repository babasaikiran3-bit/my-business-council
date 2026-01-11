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
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings, generate_conversation_title, format_conversation_history

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

class UpdateTitleRequest(BaseModel):
    """Request to update conversation title."""
    title: str


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


# Add this endpoint (put it with other conversation endpoints)
@app.put("/api/conversations/{conversation_id}/title")
async def update_conversation_title_endpoint(conversation_id: str, request: UpdateTitleRequest):
    """Update conversation title manually."""
    print(f"[TITLE] Manual title update requested: {conversation_id} -> '{request.title}'")
    
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Update title in storage
    success = storage.update_conversation_title(conversation_id, request.title)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update title")
    
    return {
        "status": "success", 
        "title": request.title,
        "message": "Title updated successfully"
    }


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: str):
    """Delete a conversation."""
    print(f"[DELETE] Deleting conversation: {conversation_id}")
    
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Delete the conversation
    success = storage.delete_conversation(conversation_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete conversation")
    
    return {
        "status": "success",
        "message": f"Conversation '{conversation.get('title', conversation_id)}' deleted successfully",
        "deleted_id": conversation_id
    }


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Get previous messages for context (excluding the one we just added)
    previous_messages = conversation["messages"][:-1]  # All messages except the one we just added
    
    # Run the 3-stage council process WITH conversation context
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content,
        previous_messages  # Pass conversation history
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # If there are messages but no title yet
    if not is_first_message and conversation.get("title") == "New Conversation":
        recent_text = ""
        recent_msgs = conversation["messages"][-3:]  # Last 3 messages
        for msg in recent_msgs:
            if msg["role"] == "user":
                recent_text += f"User: {msg['content']}\n"
        
        if recent_text:
            title = await generate_conversation_title(recent_text)
            storage.update_conversation_title(conversation_id, title)

    return {
        "conversation_id": conversation_id,
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata,
        "is_first_message": is_first_message
    }

@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    """
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Check if this is the first message
            is_first_message = len(conversation["messages"]) == 0

            # Get previous messages for context
            previous_messages = conversation["messages"][:-1]  # All messages except the one we just added

            # Start title generation in parallel (if first message)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses WITH context
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(
                request.content, 
                format_conversation_history(previous_messages) if previous_messages else None
            )
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings WITH context
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(
                request.content, 
                stage1_results,
                format_conversation_history(previous_messages) if previous_messages else None
            )
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer WITH context
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(
                request.content,
                stage1_results,
                stage2_results,
                format_conversation_history(previous_messages) if previous_messages else None
            )
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                try:
                    title = await title_task
                    storage.update_conversation_title(conversation_id, title)
                    yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"
                except Exception as e:
                    print(f"Failed to generate title: {e}")

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
            print(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.get("/api/debug/conversations/{conversation_id}")
async def debug_conversation(conversation_id: str):
    """Debug endpoint to check conversation data."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        return {"error": "Conversation not found"}
    
    return {
        "id": conversation.get("id"),
        "title": conversation.get("title"),
        "messages_count": len(conversation.get("messages", [])),
        "created_at": conversation.get("created_at"),
        "updated_at": conversation.get("updated_at"),
        "all_data": conversation  # Be careful with large data
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
