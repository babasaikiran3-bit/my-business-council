"""JSON-based storage implementation."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .base import StorageBackend


class JSONStorageBackend(StorageBackend):
    """JSON file-based storage implementation."""

    def __init__(self, data_dir: str):
        """
        Initialize JSON storage backend.

        Args:
            data_dir: Directory to store JSON files
        """
        self.data_dir = data_dir
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Ensure the data directory exists."""
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)

    def _get_conversation_path(self, conversation_id: str) -> str:
        """Get the file path for a conversation."""
        return os.path.join(self.data_dir, f"{conversation_id}.json")

    def _load_conversation_file(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Load a conversation from file."""
        path = self._get_conversation_path(conversation_id)
        if not os.path.exists(path):
            return None

        with open(path, 'r') as f:
            return json.load(f)

    def _save_conversation_file(self, conversation: Dict[str, Any]):
        """Save a conversation to file."""
        self._ensure_data_dir()
        path = self._get_conversation_path(conversation['id'])
        with open(path, 'w') as f:
            json.dump(conversation, f, indent=2)

    def create_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Create a new conversation."""
        conversation = {
            "id": conversation_id,
            "created_at": datetime.utcnow().isoformat(),
            "title": "New Conversation",
            "messages": []
        }
        self._save_conversation_file(conversation)
        return conversation

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation by ID."""
        return self._load_conversation_file(conversation_id)

    def list_conversations(self) -> List[Dict[str, Any]]:
        """List all conversations (metadata only)."""
        self._ensure_data_dir()

        conversations = []
        for filename in os.listdir(self.data_dir):
            if filename.endswith('.json'):
                path = os.path.join(self.data_dir, filename)
                with open(path, 'r') as f:
                    data = json.load(f)
                    conversations.append({
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "title": data.get("title", "New Conversation"),
                        "message_count": len(data["messages"])
                    })

        # Sort by creation time, newest first
        conversations.sort(key=lambda x: x["created_at"], reverse=True)
        return conversations

    def add_user_message(self, conversation_id: str, content: str) -> None:
        """Add a user message to a conversation."""
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation["messages"].append({
            "role": "user",
            "content": content
        })
        self._save_conversation_file(conversation)

    def add_assistant_message(
        self,
        conversation_id: str,
        stage1_results: List[Dict[str, Any]],
        stage2_results: List[Dict[str, Any]],
        stage3_result: Dict[str, Any]
    ) -> None:
        """Add an assistant message with all council stages."""
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation["messages"].append({
            "role": "assistant",
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result
        })
        self._save_conversation_file(conversation)

    def update_conversation_title(self, conversation_id: str, title: str) -> None:
        """Update the title of a conversation."""
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation["title"] = title
        self._save_conversation_file(conversation)

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        path = self._get_conversation_path(conversation_id)
        if not os.path.exists(path):
            return False

        os.remove(path)
        return True

    def search_conversations(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search conversations by content (simple implementation).

        Note: This is a basic search implementation. For production use,
        consider migrating to SQLite with FTS5 for better performance.
        """
        query_lower = query.lower()
        matching_conversations = []

        for filename in os.listdir(self.data_dir):
            if not filename.endswith('.json'):
                continue

            path = os.path.join(self.data_dir, filename)
            with open(path, 'r') as f:
                data = json.load(f)

                # Search in title
                if query_lower in data.get("title", "").lower():
                    matching_conversations.append({
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "title": data.get("title", "New Conversation"),
                        "message_count": len(data["messages"])
                    })
                    continue

                # Search in message content
                for message in data["messages"]:
                    if message["role"] == "user":
                        if query_lower in message.get("content", "").lower():
                            matching_conversations.append({
                                "id": data["id"],
                                "created_at": data["created_at"],
                                "title": data.get("title", "New Conversation"),
                                "message_count": len(data["messages"])
                            })
                            break

        # Sort by creation time, newest first, and limit results
        matching_conversations.sort(key=lambda x: x["created_at"], reverse=True)
        return matching_conversations[:limit]

    def get_conversation_costs(self, conversation_id: str) -> Dict[str, float]:
        """Get cost statistics for a conversation."""
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            return {"total_usd": 0.0}

        total_cost = 0.0
        stage_costs = {"stage1_usd": 0.0, "stage2_usd": 0.0, "stage3_usd": 0.0}

        for message in conversation["messages"]:
            if message["role"] == "assistant":
                # Sum up costs from all stages
                if "stage1" in message:
                    for response in message["stage1"]:
                        stage_costs["stage1_usd"] += response.get("cost_usd", 0.0)

                if "stage2" in message:
                    for ranking in message["stage2"]:
                        stage_costs["stage2_usd"] += ranking.get("cost_usd", 0.0)

                if "stage3" in message:
                    stage_costs["stage3_usd"] += message["stage3"].get("cost_usd", 0.0)

        total_cost = sum(stage_costs.values())

        return {
            "total_usd": round(total_cost, 6),
            **{k: round(v, 6) for k, v in stage_costs.items()}
        }

    def get_total_costs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get total costs across all conversations."""
        total_cost = 0.0
        conversation_count = 0
        stage_costs = {"stage1_usd": 0.0, "stage2_usd": 0.0, "stage3_usd": 0.0}

        for filename in os.listdir(self.data_dir):
            if not filename.endswith('.json'):
                continue

            path = os.path.join(self.data_dir, filename)
            with open(path, 'r') as f:
                data = json.load(f)

                # Filter by date if specified
                created_at = datetime.fromisoformat(data["created_at"])
                if start_date and created_at < start_date:
                    continue
                if end_date and created_at > end_date:
                    continue

                conversation_count += 1
                conv_costs = self.get_conversation_costs(data["id"])
                total_cost += conv_costs["total_usd"]
                for key in stage_costs:
                    stage_costs[key] += conv_costs.get(key, 0.0)

        return {
            "total_usd": round(total_cost, 6),
            "conversation_count": conversation_count,
            **{k: round(v, 6) for k, v in stage_costs.items()}
        }
