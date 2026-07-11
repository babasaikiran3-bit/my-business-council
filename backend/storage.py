"""SQLite-based storage for conversations.

Esquema:
  conversations(id TEXT PK, created_at TEXT, title TEXT)
  messages(id INTEGER PK, conversation_id TEXT FK, position INT, role TEXT, data TEXT/JSON)

`data` (JSON) por rol:
  user      -> {"content": "..."}
  assistant -> {"stage1": [...], "stage2": [...], "stage3": {...}, "metadata": {...}}

La interfaz pública es idéntica a la versión JSON previa; el resto del backend no cambia.
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

from .config import DB_PATH


# --- Conexión / esquema -----------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crea las tablas si no existen. Idempotente."""
    import os
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id         TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                title      TEXT NOT NULL DEFAULT 'New Conversation',
                repo_path  TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                position        INTEGER NOT NULL,
                role            TEXT NOT NULL,
                data            TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conv
                ON messages(conversation_id, position);
            """
        )
        # Migración para DBs creadas antes de la columna repo_path.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        if "repo_path" not in cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN repo_path TEXT")


# --- Helpers ----------------------------------------------------------------

def _row_to_message(row: sqlite3.Row) -> Dict[str, Any]:
    data = json.loads(row["data"])
    return {"role": row["role"], **data}


def _next_position(conn: sqlite3.Connection, conversation_id: str) -> int:
    cur = conn.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 AS pos FROM messages WHERE conversation_id = ?",
        (conversation_id,),
    )
    return cur.fetchone()["pos"]


# --- API pública ------------------------------------------------------------

def create_conversation(conversation_id: str, repo_path: Optional[str] = None) -> Dict[str, Any]:
    """Crea una conversación nueva y devuelve su dict."""
    init_db()
    created_at = datetime.utcnow().isoformat()
    title = "New Conversation"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, created_at, title, repo_path) VALUES (?, ?, ?, ?)",
            (conversation_id, created_at, title, repo_path),
        )
    return {"id": conversation_id, "created_at": created_at, "title": title,
            "repo_path": repo_path, "messages": []}


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Carga una conversación completa (con mensajes) o None si no existe."""
    with _connect() as conn:
        conv = conn.execute(
            "SELECT id, created_at, title, repo_path FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if conv is None:
            return None
        rows = conn.execute(
            "SELECT role, data FROM messages WHERE conversation_id = ? ORDER BY position",
            (conversation_id,),
        ).fetchall()
    return {
        "id": conv["id"],
        "created_at": conv["created_at"],
        "title": conv["title"],
        "repo_path": conv["repo_path"],
        "messages": [_row_to_message(r) for r in rows],
    }


def set_conversation_repo(conversation_id: str, repo_path: Optional[str]):
    """Asocia (o actualiza) el repo de una conversación."""
    with _connect() as conn:
        conn.execute("UPDATE conversations SET repo_path = ? WHERE id = ?",
                     (repo_path, conversation_id))


def save_conversation(conversation: Dict[str, Any]):
    """Reescribe una conversación entera (upsert). Poco usado; se mantiene por compatibilidad."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, created_at, title, repo_path) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET created_at=excluded.created_at, "
            "title=excluded.title, repo_path=excluded.repo_path",
            (conversation["id"], conversation["created_at"],
             conversation.get("title", "New Conversation"),
             conversation.get("repo_path")),
        )
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation["id"],))
        for pos, msg in enumerate(conversation.get("messages", [])):
            role = msg["role"]
            data = {k: v for k, v in msg.items() if k != "role"}
            conn.execute(
                "INSERT INTO messages (conversation_id, position, role, data) VALUES (?, ?, ?, ?)",
                (conversation["id"], pos, role, json.dumps(data)),
            )


def list_conversations() -> List[Dict[str, Any]]:
    """Metadata de todas las conversaciones, más nuevas primero."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.created_at, c.title, c.repo_path,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
            FROM conversations c
            ORDER BY c.created_at DESC
            """
        ).fetchall()
    return [
        {"id": r["id"], "created_at": r["created_at"], "title": r["title"],
         "repo_path": r["repo_path"], "message_count": r["message_count"]}
        for r in rows
    ]


def delete_conversation(conversation_id: str) -> bool:
    """Borra una conversación y sus mensajes. Devuelve True si existía."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        return cur.rowcount > 0


def add_user_message(conversation_id: str, content: str):
    """Agrega un mensaje del usuario."""
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM conversations WHERE id = ?",
                        (conversation_id,)).fetchone() is None:
            raise ValueError(f"Conversation {conversation_id} not found")
        pos = _next_position(conn, conversation_id)
        conn.execute(
            "INSERT INTO messages (conversation_id, position, role, data) VALUES (?, ?, 'user', ?)",
            (conversation_id, pos, json.dumps({"content": content})),
        )


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
):
    """Agrega un mensaje del asistente con las 3 etapas (y opcionalmente metadata)."""
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM conversations WHERE id = ?",
                        (conversation_id,)).fetchone() is None:
            raise ValueError(f"Conversation {conversation_id} not found")
        pos = _next_position(conn, conversation_id)
        data = {"stage1": stage1, "stage2": stage2, "stage3": stage3}
        if metadata is not None:
            data["metadata"] = metadata
        conn.execute(
            "INSERT INTO messages (conversation_id, position, role, data) VALUES (?, ?, 'assistant', ?)",
            (conversation_id, pos, json.dumps(data)),
        )


def update_conversation_title(conversation_id: str, title: str):
    """Actualiza el título de una conversación."""
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM conversations WHERE id = ?",
                        (conversation_id,)).fetchone() is None:
            raise ValueError(f"Conversation {conversation_id} not found")
        conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
