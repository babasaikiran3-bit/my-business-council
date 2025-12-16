"""User-scoped JSON storage for conversations."""

import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR


# Directory structure:
# data/users/{user_id}/conversations/{conversation_id}.json


def sanitize_user_id(user_id: str) -> str:
    """Sanitize user_id to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]+$', user_id):
        raise ValueError(f"Invalid user_id format: {user_id}")
    return user_id


def get_user_data_dir(user_id: str) -> str:
    """Get the data directory for a specific user."""
    user_id = sanitize_user_id(user_id)
    return os.path.join(DATA_DIR, "users", user_id, "conversations")


def ensure_user_data_dir(user_id: str):
    """Ensure the user's data directory exists."""
    Path(get_user_data_dir(user_id)).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str, user_id: str) -> str:
    """Get the file path for a user's conversation."""
    return os.path.join(get_user_data_dir(user_id), f"{conversation_id}.json")


def create_conversation(conversation_id: str, user_id: str) -> Dict[str, Any]:
    """
    Create a new conversation for a user.

    Args:
        conversation_id: Unique identifier for the conversation
        user_id: WorkOS user ID for scoping

    Returns:
        New conversation dict
    """
    ensure_user_data_dir(user_id)

    conversation = {
        "id": conversation_id,
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "messages": []
    }

    # Save to file
    path = get_conversation_path(conversation_id, user_id)
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)

    return conversation


def get_conversation(conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation
        user_id: WorkOS user ID for scoping

    Returns:
        Conversation dict or None if not found
    """
    path = get_conversation_path(conversation_id, user_id)

    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any], user_id: str):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
        user_id: WorkOS user ID for scoping
    """
    ensure_user_data_dir(user_id)

    path = get_conversation_path(conversation['id'], user_id)
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)


def list_conversations(user_id: str) -> List[Dict[str, Any]]:
    """
    List all conversations for a user (metadata only).

    Args:
        user_id: WorkOS user ID for scoping

    Returns:
        List of conversation metadata dicts
    """
    user_dir = get_user_data_dir(user_id)

    # Create dir if it doesn't exist
    Path(user_dir).mkdir(parents=True, exist_ok=True)

    conversations = []
    for filename in os.listdir(user_dir):
        if filename.endswith('.json'):
            path = os.path.join(user_dir, filename)
            with open(path, 'r') as f:
                data = json.load(f)
                # Return metadata only
                conversations.append({
                    "id": data["id"],
                    "created_at": data["created_at"],
                    "title": data.get("title", "New Conversation"),
                    "message_count": len(data["messages"])
                })

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    return conversations


def add_user_message(conversation_id: str, user_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        user_id: WorkOS user ID for scoping
        content: User message content
    """
    conversation = get_conversation(conversation_id, user_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "user",
        "content": content
    })

    save_conversation(conversation, user_id)


def add_assistant_message(
    conversation_id: str,
    user_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        user_id: WorkOS user ID for scoping
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
    """
    conversation = get_conversation(conversation_id, user_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3
    })

    save_conversation(conversation, user_id)


def update_conversation_title(conversation_id: str, user_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        user_id: WorkOS user ID for scoping
        title: New title for the conversation
    """
    conversation = get_conversation(conversation_id, user_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation, user_id)
