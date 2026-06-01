"""Tenant-aware storage behind an operations-shaped abstraction.

Phase 1a of the SaaS migration. Every operation is partitioned by ``user_id`` so no
user can read another's data — the multi-tenant spine the consensus review required
(the old module globbed a single global directory). The interface is drawn around
*operations* (append/list/get), NOT the old read-whole-file→mutate→write functions,
so a Postgres backend can later implement the same contract without inheriting the
JSON file pattern. Select the backend via the ``STORAGE_BACKEND`` env var; JSON is the
default so the app runs with no external database.

Durability (pilot, single-worker JSON backend):
- Writes are atomic: a temp file is fsync'd then ``os.replace``-d into place, so a crash
  mid-write never corrupts the live file (the previous valid version survives).
- Each per-conversation read→mutate→write is serialised by a per-key ``asyncio.Lock``
  held across the whole operation; the synchronous file write runs off the event loop via
  ``asyncio.to_thread`` so concurrent SSE streams are never blocked. The lock — NOT the
  ``flock`` below — is the load-bearing in-process guard against lost updates.
- An advisory ``fcntl.flock`` is taken inside the write as a crash/inter-process backstop
  (cheap insurance if the single-worker mandate is ever violated). POSIX/Linux only.
- Reads tolerate corruption: a malformed file is quarantined (``*.json.corrupted``) and
  skipped rather than 500-ing a whole listing.
The app MUST run single-worker with ``DATA_DIR`` on a persistent disk (see DEPLOYMENT.md).
"""

import asyncio
import json
import os
import re
import uuid
import weakref
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # POSIX advisory locking (Linux/macOS). Absent on Windows — flock becomes a no-op.
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]

from .config import DATA_DIR

# user_id and conversation_id are used in filesystem paths — allow only safe chars
# so a crafted id can never traverse outside a user's directory.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class StorageCorruptionError(Exception):
    """Raised when a single requested record exists but cannot be parsed."""


def _is_safe_id(value: str) -> bool:
    return bool(value) and bool(_SAFE_ID_RE.match(value))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, obj: Any) -> None:
    """Durably write ``obj`` as JSON to ``path`` (temp + fsync + atomic replace).

    Synchronous by design (callers run it via ``asyncio.to_thread`` to stay off the event
    loop). An advisory ``flock`` on a sidecar ``.lock`` file guards against a second OS
    process writing the same file concurrently — a backstop for the single-worker mandate.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp.{uuid.uuid4().hex}")
    lock_path = path.with_name(f"{path.name}.lock")
    lock_f = open(lock_path, "w")
    try:
        if fcntl is not None:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            with open(tmp_path, "w") as f:
                json.dump(obj, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)  # atomic on POSIX
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
    finally:
        if fcntl is not None:
            try:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        lock_f.close()


class KeyedLocks:
    """Per-key ``asyncio.Lock`` registry shared by the JSON stores + quota.

    A ``WeakValueDictionary`` so idle locks are GC'd (no unbounded growth); an in-use lock
    is strongly referenced on the awaiting stack so it cannot be evicted mid-operation.
    ``__call__`` runs synchronously (no await), so get-or-create is atomic w.r.t. the loop.
    """

    def __init__(self) -> None:
        self._locks: "weakref.WeakValueDictionary[str, asyncio.Lock]" = weakref.WeakValueDictionary()

    def __call__(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock


def _read_json_or_quarantine(path: Path) -> Any:
    """Read+parse JSON. On corruption, rename to ``*.json.corrupted`` and raise.

    Quarantine (rather than delete) preserves the bytes for forensic/recovery while
    ensuring the same broken file is not retried on every request.
    """
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        corrupt = path.with_name(f"{path.name}.corrupted")
        try:
            os.replace(path, corrupt)
        except OSError:
            pass
        raise StorageCorruptionError(str(path)) from e


class StorageBackend(ABC):
    """Operations-shaped, per-user storage contract.

    Mutating ops are ``async`` so a backend can serialise a read→mutate→write across an
    ``await`` (the JSON backend holds a per-key lock; a Postgres backend would use a
    transaction). Read ops stay sync — a single atomic read needs no cross-await guard.
    """

    @abstractmethod
    def create_conversation(self, user_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def list_conversations(self, user_id: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def append_user_message(self, user_id: str, conversation_id: str, content: str) -> None: ...

    @abstractmethod
    async def append_assistant_message(
        self, user_id: str, conversation_id: str,
        stage0: Dict[str, Any], stage1: List[Dict[str, Any]],
        stage2: List[Dict[str, Any]], stage3: Dict[str, Any],
        short_circuit: bool = False, idempotency_key: Optional[str] = None,
    ) -> None: ...

    @abstractmethod
    async def update_title(self, user_id: str, conversation_id: str, title: str) -> None: ...

    @abstractmethod
    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool: ...


# Minimal shape a conversation file must have to be served (schema guard on load).
_CONVERSATION_KEYS = ("id", "user_id", "messages")


class JsonStorageBackend(StorageBackend):
    """JSON-file backend partitioned as ``{data_dir}/{user_id}/{conversation_id}.json``.

    Isolation is structural: every path is built from the authenticated ``user_id``, so
    ``get_conversation(user_id, id)`` can only ever read inside that user's directory.
    """

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self._lock_for = KeyedLocks()  # per-conversation locks

    def _user_dir(self, user_id: str) -> Path:
        if not _is_safe_id(user_id):
            raise ValueError("invalid user_id")
        return Path(self.data_dir) / user_id

    def _path(self, user_id: str, conversation_id: str) -> Optional[Path]:
        if not _is_safe_id(conversation_id):
            return None
        return self._user_dir(user_id) / f"{conversation_id}.json"

    def _save(self, conversation: Dict[str, Any]) -> None:
        path = self._user_dir(conversation["user_id"]) / f"{conversation['id']}.json"
        _atomic_write_json(path, conversation)

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
        data = _read_json_or_quarantine(path)
        if not isinstance(data, dict) or not all(k in data for k in _CONVERSATION_KEYS):
            corrupt = path.with_name(f"{path.name}.corrupted")
            try:
                os.replace(path, corrupt)
            except OSError:
                pass
            raise StorageCorruptionError(str(path))
        return data

    def list_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return []
        conversations = []
        for entry in user_dir.glob("*.json"):
            try:
                data = _read_json_or_quarantine(entry)
            except StorageCorruptionError:
                continue  # one bad file never breaks the whole listing
            if not isinstance(data, dict) or "id" not in data or "created_at" not in data:
                continue
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

    async def append_user_message(self, user_id: str, conversation_id: str, content: str) -> None:
        async with self._lock_for(f"{user_id}/{conversation_id}"):
            conversation = self._load_owned(user_id, conversation_id)
            conversation["messages"].append({"role": "user", "content": content})
            await asyncio.to_thread(self._save, conversation)

    async def append_assistant_message(
        self, user_id: str, conversation_id: str,
        stage0: Dict[str, Any], stage1: List[Dict[str, Any]],
        stage2: List[Dict[str, Any]], stage3: Dict[str, Any],
        short_circuit: bool = False, idempotency_key: Optional[str] = None,
    ) -> None:
        async with self._lock_for(f"{user_id}/{conversation_id}"):
            conversation = self._load_owned(user_id, conversation_id)
            message: Dict[str, Any] = {
                "role": "assistant",
                "stage0": stage0,
                "stage1": stage1,
                "stage2": stage2,
                "stage3": stage3,
            }
            if short_circuit:
                # Single named shape for both triage short-circuits and mid-pipeline
                # partial saves: the frontend keys on this to render triage-only (no
                # empty Stage0/1/2 panels) on reload.
                message["short_circuit"] = True
            if idempotency_key:
                message["idempotency_key"] = idempotency_key
            conversation["messages"].append(message)
            await asyncio.to_thread(self._save, conversation)

    async def update_title(self, user_id: str, conversation_id: str, title: str) -> None:
        async with self._lock_for(f"{user_id}/{conversation_id}"):
            conversation = self._load_owned(user_id, conversation_id)
            conversation["title"] = title
            await asyncio.to_thread(self._save, conversation)

    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        async with self._lock_for(f"{user_id}/{conversation_id}"):
            path = self._path(user_id, conversation_id)
            if path is None or not path.exists():
                return False
            await asyncio.to_thread(os.remove, path)
            return True


def _build_backend() -> StorageBackend:
    kind = os.getenv("STORAGE_BACKEND", "json").lower()
    if kind == "json":
        return JsonStorageBackend()
    # Postgres backend is added in a later phase behind this same interface.
    raise ValueError(f"Unknown STORAGE_BACKEND: {kind!r}")


# Process-wide store selected by env (defaults to runnable, no-DB JSON).
store: StorageBackend = _build_backend()
