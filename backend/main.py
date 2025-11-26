"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio
from redis import Redis
from rq import Queue

from . import storage, jobs
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings
from .config import REDIS_URL, get_council_config, update_council_config as config_update_council
from .worker import process_council_job
from .openrouter import close_http_client
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle - startup and shutdown."""
    yield
    # Cleanup on shutdown
    await close_http_client()


app = FastAPI(title="LLM Council API", lifespan=lifespan)

# Initialize Redis connection and RQ queue
redis_conn = Redis.from_url(REDIS_URL)
task_queue = Queue("council", connection=redis_conn)

# Enable CORS for local and network development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
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


class CouncilConfigRequest(BaseModel):
    """Request to update council configuration."""
    council_models: List[str] = None
    chairman_model: str = None
    custom_models: List[str] = None


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int
    total_cost: float


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


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    storage.delete_conversation(conversation_id)
    return {"message": "Conversation deleted successfully"}


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
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata, total_cost = await run_full_council(
        request.content
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )
    
    # Update conversation cost
    storage.add_cost_to_conversation(conversation_id, total_cost)

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata,
        "cost": total_cost
    }


@app.post("/api/conversations/{conversation_id}/message/async")
async def send_message_async(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and process it in the background.
    Returns immediately with a job_id that can be used to check status.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Generate title BEFORE adding user message to avoid race condition
    title = None
    if is_first_message:
        try:
            title = await generate_conversation_title(request.content)
            storage.update_conversation_title(conversation_id, title)
        except Exception as e:
            print(f"⚠️ Failed to generate title: {e}")

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Create job record
    jobs.create_job(job_id, conversation_id, request.content)

    # Enqueue the job for background processing
    rq_job = task_queue.enqueue(
        process_council_job,
        job_id,
        conversation_id,
        request.content,
        job_timeout='30m'
    )
    
    # Store RQ job ID for cancellation
    jobs.update_job_status(job_id, "pending", rq_job_id=rq_job.id)

    response = {
        "job_id": job_id,
        "status": "pending",
        "message": "Job queued for processing"
    }
    
    # Include title if generated
    if title:
        response["title"] = title
    
    return response


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status and result of a background job.
    """
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel a pending or processing job.
    """
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job['status'] not in ('pending', 'processing'):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job with status: {job['status']}")
    
    # Try to cancel the RQ job using stored rq_job_id
    rq_job_id = job.get('rq_job_id')
    if rq_job_id:
        try:
            from rq.job import Job as RQJob
            rq_job = RQJob.fetch(rq_job_id, connection=redis_conn)
            if rq_job:
                rq_job.cancel()
                print(f"✓ Cancelled RQ job {rq_job_id}")
        except Exception as e:
            print(f"⚠️ Could not cancel RQ job {rq_job_id}: {e}")
    else:
        print(f"⚠️ No rq_job_id found for job {job_id}")
    
    # Update job status
    jobs.update_job_status(job_id, "failed", error="Cancelled by user")
    
    return {"status": "cancelled", "job_id": job_id}


@app.post("/api/conversations/{conversation_id}/retry")
async def retry_last_message(conversation_id: str):
    """
    Retry the last failed message in a conversation.
    Removes the failed assistant message and requeues the user's question.
    """
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = conversation.get("messages", [])
    if len(messages) < 1:
        raise HTTPException(status_code=400, detail="No message to retry")
    
    # Find the last user message
    last_user_msg = None
    last_user_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i]['role'] == 'user':
            last_user_msg = messages[i]
            last_user_idx = i
            break
    
    if last_user_msg is None:
        raise HTTPException(status_code=400, detail="No user message found to retry")
    
    # Remove messages after the last user message (keep the user message)
    conversation["messages"] = messages[:last_user_idx + 1]
    storage.save_conversation(conversation)
    
    # Re-submit the message
    job_id = str(uuid.uuid4())
    jobs.create_job(job_id, conversation_id, last_user_msg['content'])
    
    # Enqueue the job
    task_queue.enqueue(
        process_council_job,
        job_id,
        conversation_id,
        last_user_msg['content'],
        job_timeout='30m'
    )
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Retry queued for processing"
    }


@app.get("/api/config/council")
async def get_council_config_endpoint():
    """Get current council configuration."""
    return get_council_config()


@app.post("/api/config/council")
async def update_council_config_endpoint(request: CouncilConfigRequest):
    """Update council configuration."""
    updated = config_update_council(
        council_models=request.council_models,
        chairman_model=request.chairman_model,
        custom_models=request.custom_models
    )
    return updated


class VerifyModelRequest(BaseModel):
    """Request to verify a model."""
    model: str


@app.post("/api/models/verify")
async def verify_model(request: VerifyModelRequest):
    """
    Verify that a model is callable on OpenRouter.
    Makes a minimal test request to check if the model is available.
    """
    from .openrouter import query_model
    
    # Use a minimal test message
    test_messages = [{"role": "user", "content": "Hi"}]
    
    try:
        # Short timeout for verification
        response = await query_model(
            request.model, 
            test_messages, 
            timeout=15.0,
            max_tokens=5  # Minimal tokens to save cost
        )
        
        if response is None:
            return {
                "valid": False,
                "error": "Model did not respond. It may be unavailable or deprecated."
            }
        
        return {
            "valid": True,
            "model": request.model
        }
        
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "not found" in error_msg.lower():
            return {"valid": False, "error": "Model not found on OpenRouter."}
        elif "401" in error_msg or "403" in error_msg:
            return {"valid": False, "error": "Model requires special access or payment."}
        elif "rate" in error_msg.lower():
            return {"valid": False, "error": "Rate limited. Try again later."}
        else:
            return {"valid": False, "error": f"Verification failed: {error_msg}"}


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
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Track total cost
            total_cost = 0.0
            
            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results, stage1_cost, _ = await stage1_collect_responses(request.content)
            total_cost += stage1_cost
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model, stage2_cost, _ = await stage2_collect_rankings(request.content, stage1_results)
            total_cost += stage2_cost
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result, stage3_cost, _ = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            total_cost += stage3_cost
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

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
            
            # Update conversation cost
            storage.add_cost_to_conversation(conversation_id, total_cost)

            # Send completion event with cost
            yield f"data: {json.dumps({'type': 'complete', 'cost': total_cost})}\n\n"

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
