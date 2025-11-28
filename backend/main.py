"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any
import uuid
import json
import asyncio
import re

from . import storage
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings
from .logging_config import configure_logging, get_logger
from .config import LOG_LEVEL
from .github_client import get_github_client
from .storage.models import Repository, ConversationRepository
from .storage.sqlite_storage import SQLiteStorageBackend

# Configure logging
configure_logging(log_level=LOG_LEVEL)
logger = get_logger(__name__)

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
    content: str = Field(
        min_length=1,
        max_length=10000,
        description="The message content"
    )

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate and sanitize message content."""
        # Strip whitespace
        v = v.strip()

        # Check if empty after stripping
        if not v:
            raise ValueError('Message cannot be empty or contain only whitespace')

        # Check for excessively long lines (potential abuse)
        lines = v.split('\n')
        if any(len(line) > 5000 for line in lines):
            raise ValueError('Individual lines cannot exceed 5000 characters')

        # Limit number of newlines (prevent abuse)
        if v.count('\n') > 500:
            raise ValueError('Message cannot exceed 500 lines')

        return v


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


def validate_conversation_id(conversation_id: str) -> str:
    """
    Validate conversation ID to prevent path traversal and injection attacks.

    Args:
        conversation_id: The conversation ID to validate

    Returns:
        The validated conversation ID

    Raises:
        HTTPException: If the conversation ID is invalid
    """
    # Allow only UUID-like strings (alphanumeric and hyphens)
    if not re.match(r'^[a-zA-Z0-9\-]+$', conversation_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation ID format"
        )

    # Prevent path traversal attempts
    if '..' in conversation_id or '/' in conversation_id or '\\' in conversation_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation ID format"
        )

    # Limit length to reasonable UUID size
    if len(conversation_id) > 100:
        raise HTTPException(
            status_code=400,
            detail="Conversation ID too long"
        )

    return conversation_id


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation_id = validate_conversation_id(conversation_id)
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
    # Validate conversation ID
    conversation_id = validate_conversation_id(conversation_id)

    logger.info(
        "message_received",
        conversation_id=conversation_id,
        message_length=len(request.content)
    )

    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Fetch attached repositories and build context
    repo_context = None
    backend = storage.get_storage_backend()
    if isinstance(backend, SQLiteStorageBackend):
        session = backend.SessionLocal()
        try:
            conv_repos = session.query(ConversationRepository).filter_by(
                conversation_id=conversation_id
            ).all()

            if conv_repos:
                repo_summaries = []
                for conv_repo in conv_repos:
                    repo = session.query(Repository).filter_by(id=conv_repo.repository_id).first()
                    if repo and repo.summary:
                        repo_summaries.append(repo.summary)

                if repo_summaries:
                    repo_context = "# Repository Context\n\n" + "\n\n---\n\n".join(repo_summaries)
                    logger.info("repo_context_loaded", conversation_id=conversation_id, repos_count=len(repo_summaries))

        finally:
            session.close()

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process (with optional repo context)
    logger.info("council_process_starting", conversation_id=conversation_id)
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content,
        repo_context
    )
    logger.info(
        "council_process_complete",
        conversation_id=conversation_id,
        stage1_responses=len(stage1_results),
        stage2_rankings=len(stage2_results)
    )

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
    # Validate conversation ID
    conversation_id = validate_conversation_id(conversation_id)

    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Fetch attached repositories and build context
    repo_context = None
    backend = storage.get_storage_backend()
    if isinstance(backend, SQLiteStorageBackend):
        session = backend.SessionLocal()
        try:
            conv_repos = session.query(ConversationRepository).filter_by(
                conversation_id=conversation_id
            ).all()

            if conv_repos:
                repo_summaries = []
                for conv_repo in conv_repos:
                    repo = session.query(Repository).filter_by(id=conv_repo.repository_id).first()
                    if repo and repo.summary:
                        repo_summaries.append(repo.summary)

                if repo_summaries:
                    repo_context = "# Repository Context\n\n" + "\n\n---\n\n".join(repo_summaries)
                    logger.info("repo_context_loaded", conversation_id=conversation_id, repos_count=len(repo_summaries))

        finally:
            session.close()

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses (with optional repo context)
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content, repo_context)
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

            # Calculate and send cost information
            stage1_cost = sum(r.get('cost_usd', 0.0) for r in stage1_results)
            stage2_cost = sum(r.get('cost_usd', 0.0) for r in stage2_results)
            stage3_cost = stage3_result.get('cost_usd', 0.0)
            total_cost = stage1_cost + stage2_cost + stage3_cost

            costs = {
                'stage1_usd': round(stage1_cost, 6),
                'stage2_usd': round(stage2_cost, 6),
                'stage3_usd': round(stage3_cost, 6),
                'total_usd': round(total_cost, 6)
            }
            yield f"data: {json.dumps({'type': 'costs', 'data': costs})}\n\n"

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


# ============================================================================
# GitHub Integration Endpoints
# ============================================================================

@app.get("/api/github/repos")
async def list_github_repos():
    """
    List GitHub repositories for the authenticated user.

    Requires GITHUB_TOKEN to be configured in .env
    """
    github_client = get_github_client()

    if not github_client.is_available():
        raise HTTPException(
            status_code=503,
            detail="GitHub integration not configured. Please set GITHUB_TOKEN in .env"
        )

    repos = github_client.get_user_repos(limit=100)
    logger.info("listed_github_repos", count=len(repos))

    return {"repos": repos}


@app.post("/api/conversations/{conversation_id}/repos/{repo_full_name}")
async def attach_repo_to_conversation(conversation_id: str, repo_full_name: str):
    """
    Attach a GitHub repository to a conversation.

    This fetches and caches the repository content for use in council discussions.

    Args:
        conversation_id: ID of the conversation
        repo_full_name: Full repo name (e.g., "owner/repo")
    """
    # Validate conversation ID
    conversation_id = validate_conversation_id(conversation_id)

    # URL decode repo_full_name
    from urllib.parse import unquote
    repo_full_name = unquote(repo_full_name)

    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    github_client = get_github_client()
    if not github_client.is_available():
        raise HTTPException(status_code=503, detail="GitHub integration not configured")

    # Get or create repository in database
    backend = storage.get_storage_backend()
    if not isinstance(backend, SQLiteStorageBackend):
        raise HTTPException(status_code=501, detail="GitHub integration requires SQLite storage backend")

    session = backend.SessionLocal()
    try:
        # Check if repo already exists in DB
        repo_db = session.query(Repository).filter_by(full_name=repo_full_name).first()

        if not repo_db:
            # Fetch repo metadata from GitHub
            logger.info("fetching_new_repo", repo=repo_full_name)
            repo_metadata = github_client.get_repo(repo_full_name)

            if not repo_metadata:
                raise HTTPException(status_code=404, detail=f"Repository '{repo_full_name}' not found on GitHub")

            # Fetch repo structure and key files
            tree = github_client.get_repo_tree(repo_full_name)
            key_files = github_client.get_key_files(repo_full_name)
            summary = github_client.generate_repo_summary(repo_metadata, key_files, tree)

            # Create repository in DB
            repo_db = Repository(
                full_name=repo_metadata['full_name'],
                name=repo_metadata['name'],
                description=repo_metadata.get('description'),
                language=repo_metadata.get('language'),
                default_branch=repo_metadata.get('default_branch', 'main'),
                stars=repo_metadata.get('stars', 0),
                tree_structure=tree,
                key_files=key_files,
                summary=summary
            )
            session.add(repo_db)
            session.flush()  # Get the ID

        # Check if already attached
        existing = session.query(ConversationRepository).filter_by(
            conversation_id=conversation_id,
            repository_id=repo_db.id
        ).first()

        if existing:
            session.close()
            return {"message": "Repository already attached", "repository": repo_db.to_dict()}

        # Attach repo to conversation
        conv_repo = ConversationRepository(
            conversation_id=conversation_id,
            repository_id=repo_db.id
        )
        session.add(conv_repo)
        session.commit()

        logger.info("repo_attached", conversation_id=conversation_id, repo=repo_full_name)

        return {
            "message": "Repository attached successfully",
            "repository": repo_db.to_dict()
        }

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        logger.error("attach_repo_failed", conversation_id=conversation_id, repo=repo_full_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/conversations/{conversation_id}/repos")
async def list_conversation_repos(conversation_id: str):
    """
    List all repositories attached to a conversation.

    Args:
        conversation_id: ID of the conversation
    """
    # Validate conversation ID
    conversation_id = validate_conversation_id(conversation_id)

    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    backend = storage.get_storage_backend()
    if not isinstance(backend, SQLiteStorageBackend):
        return {"repos": []}

    session = backend.SessionLocal()
    try:
        # Get all repos attached to this conversation
        conv_repos = session.query(ConversationRepository).filter_by(
            conversation_id=conversation_id
        ).all()

        repos = []
        for conv_repo in conv_repos:
            repo = session.query(Repository).filter_by(id=conv_repo.repository_id).first()
            if repo:
                repos.append({
                    **repo.to_dict(),
                    "attached_at": conv_repo.attached_at.isoformat()
                })

        return {"repos": repos}

    finally:
        session.close()


@app.delete("/api/conversations/{conversation_id}/repos/{repo_full_name}")
async def detach_repo_from_conversation(conversation_id: str, repo_full_name: str):
    """
    Detach a repository from a conversation.

    Args:
        conversation_id: ID of the conversation
        repo_full_name: Full repo name (e.g., "owner/repo")
    """
    # Validate conversation ID
    conversation_id = validate_conversation_id(conversation_id)

    # URL decode repo_full_name
    from urllib.parse import unquote
    repo_full_name = unquote(repo_full_name)

    backend = storage.get_storage_backend()
    if not isinstance(backend, SQLiteStorageBackend):
        raise HTTPException(status_code=501, detail="GitHub integration requires SQLite storage backend")

    session = backend.SessionLocal()
    try:
        # Find the repository
        repo_db = session.query(Repository).filter_by(full_name=repo_full_name).first()

        if not repo_db:
            raise HTTPException(status_code=404, detail=f"Repository '{repo_full_name}' not found")

        # Find and delete the attachment
        conv_repo = session.query(ConversationRepository).filter_by(
            conversation_id=conversation_id,
            repository_id=repo_db.id
        ).first()

        if not conv_repo:
            raise HTTPException(status_code=404, detail="Repository not attached to this conversation")

        session.delete(conv_repo)
        session.commit()

        logger.info("repo_detached", conversation_id=conversation_id, repo=repo_full_name)

        return {"message": "Repository detached successfully"}

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        logger.error("detach_repo_failed", conversation_id=conversation_id, repo=repo_full_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
