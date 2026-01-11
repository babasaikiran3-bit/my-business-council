"""Conversation storage and management."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from .config import DATA_DIR


def ensure_data_dir():
    """Ensure the data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)


def get_conversation_filepath(conversation_id: str) -> str:
    """Get filepath for a conversation."""
    ensure_data_dir()
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """Create a new conversation file."""
    conversation = {
        "id": conversation_id,
        "created_at": datetime.now().isoformat(),
        "title": "New Conversation",
        "messages": [],
        "updated_at": datetime.now().isoformat(),
    }
    
    filepath = get_conversation_filepath(conversation_id)
    
    with open(filepath, 'w') as f:
        json.dump(conversation, f, indent=2, default=str)
    
    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Get a conversation by ID."""
    filepath = get_conversation_filepath(conversation_id)
    
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, 'r') as f:
            conversation = json.load(f)
        
        # Ensure all required fields exist
        conversation.setdefault("messages", [])
        conversation.setdefault("title", "New Conversation")
        
        return conversation
    except Exception as e:
        print(f"Error loading conversation {conversation_id}: {e}")
        return None


def save_conversation(conversation_id: str, conversation: Dict[str, Any]):
    """Save conversation to file."""
    filepath = get_conversation_filepath(conversation_id)
    
    # Update timestamp
    conversation["updated_at"] = datetime.now().isoformat()
    
    with open(filepath, 'w') as f:
        json.dump(conversation, f, indent=2, default=str)


def add_user_message(conversation_id: str, content: str):
    """Add a user message to conversation."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        return False
    
    message = {
        "role": "user",
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    
    conversation["messages"].append(message)
    conversation["updated_at"] = datetime.now().isoformat()
    
    save_conversation(conversation_id, conversation)
    return True


def add_assistant_message(
    conversation_id: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    stage3_result: Dict[str, Any]
):
    """Add an assistant message to conversation."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        return False
    
    message = {
        "role": "assistant",
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "timestamp": datetime.now().isoformat(),
    }
    
    conversation["messages"].append(message)
    conversation["updated_at"] = datetime.now().isoformat()
    
    save_conversation(conversation_id, conversation)
    return True


def update_conversation_title(conversation_id: str, title: str) -> bool:
    """Update conversation title."""
    print(f"[DEBUG] update_conversation_title called: id={conversation_id}, title={title}")
    
    conversation = get_conversation(conversation_id)
    if conversation is None:
        print(f"[DEBUG] Conversation {conversation_id} not found")
        return False
    
    print(f"[DEBUG] Old title: {conversation.get('title')}")
    conversation["title"] = title
    conversation["updated_at"] = datetime.now().isoformat()
    
    save_conversation(conversation_id, conversation)
    
    # Verify save
    saved_conv = get_conversation(conversation_id)
    print(f"[DEBUG] Saved title: {saved_conv.get('title')}")
    
    return True


def list_conversations() -> List[Dict[str, Any]]:
    """List all conversations (metadata only)."""
    ensure_data_dir()
    
    conversations = []
    
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(DATA_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                conversation_id = data.get("id", filename.replace(".json", ""))
                
                conversations.append({
                    "id": conversation_id,
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "title": data.get("title", "Untitled Conversation"),
                    "message_count": len(data.get("messages", [])),
                })
            except Exception as e:
                print(f"Error loading conversation file {filename}: {e}")
    
    # Sort by updated_at (most recent first)
    conversations.sort(
        key=lambda x: x.get("updated_at", ""), 
        reverse=True
    )
    
    return conversations


def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation."""
    filepath = get_conversation_filepath(conversation_id)
    
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return True
        except Exception as e:
            print(f"Error deleting conversation {conversation_id}: {e}")
    
    return False


def get_conversation_stats() -> Dict[str, Any]:
    """Get statistics about conversations."""
    conversations = list_conversations()
    
    total_conversations = len(conversations)
    total_messages = sum(conv["message_count"] for conv in conversations)
    
    return {
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "average_messages_per_conversation": total_messages / total_conversations if total_conversations > 0 else 0,
    }