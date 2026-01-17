"""Search index management using SQLite FTS5."""

import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .config import DATA_DIR

# Search database path (alongside conversation data)
SEARCH_DB_PATH = os.path.join(os.path.dirname(DATA_DIR), "search_index.db")

# Archive directory
ARCHIVE_DIR = os.path.join(os.path.dirname(DATA_DIR), "archived")


def get_connection() -> sqlite3.Connection:
    """Get a connection to the search database."""
    conn = sqlite3.connect(SEARCH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_search_db():
    """Initialize the FTS5 search database."""
    # Ensure parent directory exists
    Path(SEARCH_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS conversation_search USING fts5(
            conversation_id,
            conversation_title,
            message_id,
            role,
            content,
            is_archived,
            created_at UNINDEXED,
            tokenize='porter unicode61'
        )
    """)
    conn.commit()
    conn.close()


def index_conversation(conversation: Dict[str, Any], is_archived: bool = False):
    """
    Index a conversation's messages for search.

    Args:
        conversation: Conversation dict with messages
        is_archived: Whether this conversation is archived
    """
    conn = get_connection()
    conversation_id = conversation.get("id")
    title = conversation.get("title", "New Conversation")

    # Remove existing entries for this conversation
    conn.execute(
        "DELETE FROM conversation_search WHERE conversation_id = ?",
        (conversation_id,)
    )

    # Index conversation title as a separate entry
    conn.execute(
        """INSERT INTO conversation_search
           (conversation_id, conversation_title, message_id, role, content, is_archived, created_at)
           VALUES (?, ?, NULL, 'title', ?, ?, ?)""",
        (conversation_id, title, title, str(is_archived), conversation.get("created_at", ""))
    )

    # Index messages - handle both v1 (list) and v2 (dict) formats
    messages = conversation.get("messages", {})

    # Convert v1 list format to iterable of (id, msg) pairs
    if isinstance(messages, list):
        messages_iter = ((msg.get("id", str(i)), msg) for i, msg in enumerate(messages))
    else:
        messages_iter = messages.items()

    for msg_id, msg in messages_iter:
        role = msg.get("role")
        created_at = msg.get("created_at", "")

        if role == "user":
            # Index user message content
            content = msg.get("content", "")
            if content:
                conn.execute(
                    """INSERT INTO conversation_search
                       (conversation_id, conversation_title, message_id, role, content, is_archived, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (conversation_id, title, msg_id, role, content, str(is_archived), created_at)
                )
        elif role == "assistant":
            # Index the final synthesized answer (stage3)
            stage3 = msg.get("stage3", {})
            response = stage3.get("response", "") if isinstance(stage3, dict) else ""
            if response:
                conn.execute(
                    """INSERT INTO conversation_search
                       (conversation_id, conversation_title, message_id, role, content, is_archived, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (conversation_id, title, msg_id, role, response, str(is_archived), created_at)
                )

    conn.commit()
    conn.close()


def remove_conversation_from_index(conversation_id: str):
    """Remove a conversation from the search index."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM conversation_search WHERE conversation_id = ?",
        (conversation_id,)
    )
    conn.commit()
    conn.close()


def search(
    query: str,
    limit: int = 20,
    include_archived: bool = True
) -> List[Dict[str, Any]]:
    """
    Search conversations using simple case-insensitive text search.

    Args:
        query: Search query string
        limit: Maximum number of results
        include_archived: Whether to include archived conversations

    Returns:
        List of search results with conversation_id, message_id, snippet, rank
    """
    if not query or not query.strip():
        return []

    # Use simple LIKE search for reliability
    return search_simple(query, limit, include_archived)


def search_simple(
    query: str,
    limit: int = 20,
    include_archived: bool = True
) -> List[Dict[str, Any]]:
    """
    Simple case-insensitive search using LIKE.
    """
    conn = get_connection()

    archive_filter = ""
    if not include_archived:
        archive_filter = "AND is_archived = 'False'"

    # Use LIKE for simple substring matching (case-insensitive)
    like_pattern = f"%{query}%"

    cursor = conn.execute(f"""
        SELECT
            conversation_id,
            conversation_title,
            message_id,
            role,
            content as snippet,
            0 as rank,
            created_at
        FROM conversation_search
        WHERE content LIKE ? COLLATE NOCASE
        {archive_filter}
        LIMIT ?
    """, (like_pattern, limit))

    results = []
    for row in cursor:
        # Create a simple snippet around the match
        content = row["snippet"]
        snippet = create_snippet(content, query)
        results.append({
            "conversation_id": row["conversation_id"],
            "conversation_title": row["conversation_title"],
            "message_id": row["message_id"],
            "role": row["role"],
            "snippet": snippet,
            "rank": row["rank"],
            "created_at": row["created_at"]
        })

    conn.close()
    return results


def create_snippet(content: str, query: str, context_chars: int = 60) -> str:
    """Create a snippet with the query term highlighted."""
    if not content:
        return ""

    lower_content = content.lower()
    lower_query = query.lower()

    pos = lower_content.find(lower_query)
    if pos == -1:
        # No match found, return start of content
        return content[:context_chars * 2] + "..." if len(content) > context_chars * 2 else content

    # Calculate snippet bounds
    start = max(0, pos - context_chars)
    end = min(len(content), pos + len(query) + context_chars)

    snippet = content[start:end]

    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    # Highlight the match (case-insensitive)
    import re
    snippet = re.sub(
        re.escape(query),
        f"<mark>{query}</mark>",
        snippet,
        flags=re.IGNORECASE
    )

    return snippet


def rebuild_index() -> Dict[str, Any]:
    """
    Rebuild the entire search index from conversation files.

    Returns:
        Stats about the rebuild operation
    """
    import json
    from datetime import datetime

    start_time = datetime.now()

    # Clear existing index
    conn = get_connection()
    conn.execute("DELETE FROM conversation_search")
    conn.commit()
    conn.close()

    indexed_conversations = 0
    indexed_messages = 0

    # Index active conversations
    if os.path.exists(DATA_DIR):
        for filename in os.listdir(DATA_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(DATA_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        conversation = json.load(f)
                    index_conversation(conversation, is_archived=False)
                    indexed_conversations += 1
                    indexed_messages += len(conversation.get("messages", {}))
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error indexing {filename}: {e}")

    # Index archived conversations
    if os.path.exists(ARCHIVE_DIR):
        for filename in os.listdir(ARCHIVE_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(ARCHIVE_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        conversation = json.load(f)
                    index_conversation(conversation, is_archived=True)
                    indexed_conversations += 1
                    indexed_messages += len(conversation.get("messages", {}))
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error indexing archived {filename}: {e}")

    duration = (datetime.now() - start_time).total_seconds() * 1000

    return {
        "status": "success",
        "indexed_conversations": indexed_conversations,
        "indexed_messages": indexed_messages,
        "duration_ms": round(duration, 2)
    }


def ensure_index_exists():
    """Ensure the search index exists and is populated."""
    init_search_db()

    # Check if index is empty
    conn = get_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM conversation_search")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        # Rebuild index if empty
        rebuild_index()
