"""Database-based storage for conversations."""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, desc

from .database import AsyncSessionLocal, ConversationModel, MessageModel, init_db

logger = logging.getLogger(__name__)

async def initialize_storage():
    """Initialize the storage system (database)."""
    await init_db()

async def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Create a new conversation.
    """
    async with AsyncSessionLocal() as session:
        new_conv = ConversationModel(
            id=conversation_id,
            title="New Conversation",
            created_at=datetime.utcnow()
        )
        session.add(new_conv)
        await session.commit()
        
        return {
            "id": new_conv.id,
            "created_at": new_conv.created_at.isoformat(),
            "title": new_conv.title,
            "messages": []
        }

async def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.
    """
    async with AsyncSessionLocal() as session:
        # Get conversation
        result = await session.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        
        if not conv:
            return None
            
        # Get messages
        result = await session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at)
        )
        messages = result.scalars().all()
        
        # Format messages
        formatted_messages = []
        for msg in messages:
            if msg.role == "user":
                formatted_messages.append({
                    "role": "user",
                    "content": msg.content
                })
            elif msg.role == "assistant":
                # Reconstruct the complex assistant object
                formatted_messages.append({
                    "role": "assistant",
                    "stage1": msg.stage1_results,
                    "stage2": msg.stage2_results,
                    "stage3": msg.stage3_result,
                    "metadata": msg.metadata_json
                })
                
        return {
            "id": conv.id,
            "created_at": conv.created_at.isoformat(),
            "title": conv.title,
            "messages": formatted_messages
        }

async def get_chat_history(conversation_id: str) -> List[Dict[str, str]]:
    """
    Get simplified chat history for LLM context.
    Returns list of {'role': 'user'|'assistant', 'content': '...'}
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at)
        )
        messages = result.scalars().all()
        
        history = []
        for msg in messages:
            # For assistant messages, we use the stored 'content' (which is the final response)
            # This is much simpler than reconstructing from the complex JSON structure
            if msg.content:
                history.append({
                    "role": msg.role,
                    "content": msg.content
                })
                
        return history

async def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).
    """
    async with AsyncSessionLocal() as session:
        # Get all conversations sorted by date
        result = await session.execute(
            select(ConversationModel).order_by(desc(ConversationModel.created_at))
        )
        conversations = result.scalars().all()
        
        # For message counts, we would ideally do a join or subquery, 
        # but for simplicity effectively doing N+1 or just not showing count requires thought.
        # Let's do a simple count query for each or just skip message count for MVP speed.
        # To match previous API, we need message_count.
        
        # Let's fetch all conversations
        output = []
        for conv in conversations:
            # Count messages
            msg_count_res = await session.execute(
                select(MessageModel).where(MessageModel.conversation_id == conv.id)
            )
            count = len(msg_count_res.scalars().all())
            
            output.append({
                "id": conv.id,
                "created_at": conv.created_at.isoformat(),
                "title": conv.title,
                "message_count": count
            })
            
        return output

async def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.
    """
    async with AsyncSessionLocal() as session:
        msg = MessageModel(
            conversation_id=conversation_id,
            role="user",
            content=content,
            created_at=datetime.utcnow()
        )
        session.add(msg)
        await session.commit()

async def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    metadata: Dict[str, Any] = None
):
    """
    Add an assistant message with all 3 stages.
    """
    async with AsyncSessionLocal() as session:
        msg = MessageModel(
            conversation_id=conversation_id,
            role="assistant",
            content=stage3.get("response", ""), # Store final response as content for easy access
            stage1_results=stage1,
            stage2_results=stage2,
            stage3_result=stage3,
            metadata_json=metadata,
            created_at=datetime.utcnow()
        )
        session.add(msg)
        await session.commit()

async def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            conv.title = title
            await session.commit()
