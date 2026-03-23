"""Supabase-based storage for conversations."""

import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from .config import DATA_DIR


def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    return create_client(url, key)


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """Create a new conversation."""
    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "messages": []
    }

    get_client().table("conversations").insert(conversation).execute()
    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Load a conversation from Supabase."""
    result = (
        get_client()
        .table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def save_conversation(conversation: Dict[str, Any]):
    """Save a conversation to Supabase."""
    get_client().table("conversations").upsert(conversation).execute()


def list_conversations() -> List[Dict[str, Any]]:
    """List all conversations (metadata only)."""
    result = (
        get_client()
        .table("conversations")
        .select("id, created_at, title, messages")
        .order("created_at", desc=True)
        .execute()
    )

    conversations = []
    for data in result.data:
        conversations.append({
            "id": data["id"],
            "created_at": data["created_at"],
            "title": data.get("title", "New Conversation"),
            "message_count": len(data["messages"])
        })

    return conversations


def add_user_message(conversation_id: str, content: str):
    """Add a user message to a conversation."""
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
    """Add an assistant message with all 3 stages to a conversation."""
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
    """Update the title of a conversation."""
    get_client().table("conversations").update(
        {"title": title}
    ).eq("id", conversation_id).execute()


def record_model_appearances(models: list, rankings: list):
    """
    Record appearances and wins for all models after a council round.
    """
    client = get_client()

    for model in models:
        rank_entry = next((r for r in rankings if r["model"] == model), None)
        avg_rank = float(rank_entry["average_rank"]) if rank_entry else 0.0
        is_winner = rankings[0]["model"] == model if rankings else False

        result = client.table("model_stats").select("*").eq("model", model).execute()

        if result.data:
            existing = result.data[0]
            new_appearances = existing["total_appearances"] + 1
            new_wins = existing["wins"] + (1 if is_winner else 0)
            new_rank_points = float(existing["total_rank_points"]) + avg_rank
            new_avg_rank = round(new_rank_points / new_appearances, 2)
            new_win_rate = round(new_wins / new_appearances, 2)

            client.table("model_stats").update({
                "wins": new_wins,
                "total_appearances": new_appearances,
                "win_rate": new_win_rate,
                "avg_rank": new_avg_rank,
                "total_rank_points": new_rank_points,
                "last_updated": datetime.utcnow().isoformat()
            }).eq("model", model).execute()
        else:
            client.table("model_stats").insert({
                "model": model,
                "wins": 1 if is_winner else 0,
                "total_appearances": 1,
                "win_rate": 1.0 if is_winner else 0.0,
                "avg_rank": avg_rank,
                "total_rank_points": avg_rank,
                "last_updated": datetime.utcnow().isoformat()
            }).execute()


def get_model_stats() -> list:
    """Get all model stats sorted by win rate."""
    result = (
        get_client()
        .table("model_stats")
        .select("*")
        .order("win_rate", desc=True)
        .execute()
    )
    return result.data
