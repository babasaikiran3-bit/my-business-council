"""JSON-based storage for conversations and Discord channels."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR

# Discord-specific data directory
DISCORD_DATA_DIR = "data/discord_channels"


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Get the file path for a conversation."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        New conversation dict
    """
    ensure_data_dir()

    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "messages": []
    }

    # Save to file
    path = get_conversation_path(conversation_id)
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)

    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
    """
    ensure_data_dir()

    path = get_conversation_path(conversation['id'])
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            path = os.path.join(DATA_DIR, filename)
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


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "user",
        "content": content
    })

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3
    })

    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)


# ============================================================================
# Discord-specific storage functions
# ============================================================================

def ensure_discord_dir():
    """Ensure the Discord data directory exists."""
    Path(DISCORD_DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_discord_channel_path(channel_id: str) -> str:
    """Get the file path for a Discord channel conversation."""
    return os.path.join(DISCORD_DATA_DIR, f"{channel_id}.json")


def get_discord_channel(channel_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a Discord channel conversation from storage.

    Args:
        channel_id: Discord channel ID

    Returns:
        Channel conversation dict or None if not found
    """
    path = get_discord_channel_path(channel_id)

    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        return json.load(f)


def create_discord_channel(channel_id: str, channel_name: str = "Unknown Channel") -> Dict[str, Any]:
    """
    Create a new Discord channel conversation.

    Args:
        channel_id: Discord channel ID
        channel_name: Name of the Discord channel

    Returns:
        New channel conversation dict
    """
    ensure_discord_dir()

    channel_data = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "created_at": datetime.utcnow().isoformat(),
        "messages": []
    }

    # Save to file
    path = get_discord_channel_path(channel_id)
    with open(path, 'w') as f:
        json.dump(channel_data, f, indent=2)

    return channel_data


def save_discord_channel(channel_data: Dict[str, Any]):
    """
    Save a Discord channel conversation to storage.

    Args:
        channel_data: Channel conversation dict to save
    """
    ensure_discord_dir()

    path = get_discord_channel_path(channel_data['channel_id'])
    with open(path, 'w') as f:
        json.dump(channel_data, f, indent=2)


def add_discord_message(
    channel_id: str,
    user_id: str,
    user_name: str,
    question: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    Add a complete council interaction to a Discord channel.

    Args:
        channel_id: Discord channel ID
        user_id: Discord user ID who asked the question
        user_name: Discord username
        question: The user's question
        stage1: Stage 1 results
        stage2: Stage 2 results
        stage3: Stage 3 result
    """
    # Get or create channel data
    channel_data = get_discord_channel(channel_id)
    if channel_data is None:
        channel_data = create_discord_channel(channel_id)

    # Add the interaction
    channel_data["messages"].append({
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "user_name": user_name,
        "question": question,
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3
    })

    save_discord_channel(channel_data)


def list_discord_channels() -> List[Dict[str, Any]]:
    """
    List all Discord channels with conversation history.

    Returns:
        List of channel metadata dicts
    """
    ensure_discord_dir()

    channels = []
    for filename in os.listdir(DISCORD_DATA_DIR):
        if filename.endswith('.json'):
            path = os.path.join(DISCORD_DATA_DIR, filename)
            with open(path, 'r') as f:
                data = json.load(f)
                channels.append({
                    "channel_id": data["channel_id"],
                    "channel_name": data.get("channel_name", "Unknown"),
                    "created_at": data["created_at"],
                    "message_count": len(data["messages"])
                })

    # Sort by creation time, newest first
    channels.sort(key=lambda x: x["created_at"], reverse=True)

    return channels
