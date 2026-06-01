"""Tenant-aware storage behind an operations-shaped abstraction.

Phase 1a of the SaaS migration. Every operation is partitioned by ``user_id`` so no
user can read another's data — the multi-tenant spine the consensus review required
(the old module globbed a single global directory). The interface is drawn around
*operations* (append/list/get), NOT the old read-whole-file→mutate→write functions,
so a Postgres backend can later implement the same contract without inheriting the
JSON file pattern. Select the backend via the ``STORAGE_BACKEND`` env var; JSON is the
default so the app runs with no external database.
"""

import json
import os
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DATA_DIR

# user_id and conversation_id are used in filesystem paths — allow only safe chars
# so a crafted id can never traverse outside a user's directory.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _is_safe_id(value: str) -> bool:
    return bool(value) and bool(_SAFE_ID_RE.match(value))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StorageBackend(ABC):
    """Operations-shaped, per-user storage contract."""

    @abstractmethod
    def create_conversation(self, user_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def list_conversations(self, user_id: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def append_user_message(self, user_id: str, conversation_id: str, content: str) -> None: ...

    @abstractmethod
    def append_assistant_message(
        self, user_id: str, conversation_id: str,
        stage0: Dict[str, Any], stage1: List[Dict[str, Any]],
        stage2: List[Dict[str, Any]], stage3: Dict[str, Any],
    ) -> None: ...

    @abstractmethod
    def update_title(self, user_id: str, conversation_id: str, title: str) -> None: ...


class JsonStorageBackend(StorageBackend):
    """JSON-file backend partitioned as ``{data_dir}/{user_id}/{conversation_id}.json``.

    Isolation is structural: every path is built from the authenticated ``user_id``, so
    ``get_conversation(user_id, id)`` can only ever read inside that user's directory.
    """

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir

    def _user_dir(self, user_id: str) -> Path:
        if not _is_safe_id(user_id):
            raise ValueError("invalid user_id")
        return Path(self.data_dir) / user_id

    def _path(self, user_id: str, conversation_id: str) -> Optional[Path]:
        if not _is_safe_id(conversation_id):
            return None
        return self._user_dir(user_id) / f"{conversation_id}.json"

    def _save(self, conversation: Dict[str, Any]) -> None:
        user_dir = self._user_dir(conversation["user_id"])
        user_dir.mkdir(parents=True, exist_ok=True)
        path = user_dir / f"{conversation['id']}.json"
        with open(path, "w") as f:
            json.dump(conversation, f, indent=2, ensure_ascii=False)

    def create_conversation(self, user_id: str) -> Dict[str, Any]:
        conversation = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "created_at": _utcnow_iso(),
            "title": "New Conversation",
            "messages": [],
        }
        self._save(conversation)
        return conversation

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(user_id, conversation_id)
        if path is None or not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)

    def list_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return []
        conversations = []
        for entry in user_dir.glob("*.json"):
            with open(entry, "r") as f:
                data = json.load(f)
            conversations.append({
                "id": data["id"],
                "created_at": data["created_at"],
                "title": data.get("title", "New Conversation"),
                "message_count": len(data.get("messages", [])),
            })
        conversations.sort(key=lambda c: c["created_at"], reverse=True)
        return conversations

    def _load_owned(self, user_id: str, conversation_id: str) -> Dict[str, Any]:
        conversation = self.get_conversation(user_id, conversation_id)
        if conversation is None:
            raise KeyError(conversation_id)
        return conversation

    def append_user_message(self, user_id: str, conversation_id: str, content: str) -> None:
        conversation = self._load_owned(user_id, conversation_id)
        conversation["messages"].append({"role": "user", "content": content})
        self._save(conversation)

    def append_assistant_message(
        self, user_id: str, conversation_id: str,
        stage0: Dict[str, Any], stage1: List[Dict[str, Any]],
        stage2: List[Dict[str, Any]], stage3: Dict[str, Any],
    ) -> None:
        conversation = self._load_owned(user_id, conversation_id)
        conversation["messages"].append({
            "role": "assistant",
            "stage0": stage0,
            "stage1": stage1,
            "stage2": stage2,
            "stage3": stage3,
        })
        self._save(conversation)

    def update_title(self, user_id: str, conversation_id: str, title: str) -> None:
        conversation = self._load_owned(user_id, conversation_id)
        conversation["title"] = title
        self._save(conversation)


def _build_backend() -> StorageBackend:
    kind = os.getenv("STORAGE_BACKEND", "json").lower()
    if kind == "json":
        return JsonStorageBackend()
    # Postgres backend is added in a later phase behind this same interface.
    raise ValueError(f"Unknown STORAGE_BACKEND: {kind!r}")


# Process-wide store selected by env (defaults to runnable, no-DB JSON).
store: StorageBackend = _build_backend()
