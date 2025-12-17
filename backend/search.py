"""Typesense search integration for Eternal Ops Control.

This module provides:
- Typesense client initialization
- Collection schema definitions for conversations, messages, and zep_memories
- Indexing functions to sync Supabase data to Typesense
- Scoped API key generation for user-filtered search

Usage:
    # Initialize collections (run once on setup)
    python -m backend.search init

    # Sync all data to Typesense
    python -m backend.search sync

Security:
    - User-scoped search keys embed user_id filter at the Typesense level
    - Even if a user tries to modify search parameters, they cannot bypass the filter
    - Scoped keys expire after 1 hour for additional security
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import typesense
from typesense.exceptions import ObjectNotFound

from .config import (
    TYPESENSE_API_KEY,
    TYPESENSE_HOST,
    TYPESENSE_PORT,
    TYPESENSE_PROTOCOL,
    TYPESENSE_SEARCH_ONLY_KEY,
)

logger = logging.getLogger(__name__)

# Typesense client singleton
_typesense_client: Optional[typesense.Client] = None


# =============================================================================
# Collection Schemas
# =============================================================================

CONVERSATIONS_SCHEMA = {
    "name": "conversations",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "user_id", "type": "string", "facet": True},
        {"name": "title", "type": "string"},
        {"name": "original_query", "type": "string", "optional": True},
        {"name": "created_at", "type": "int64"},
        {"name": "source", "type": "string", "facet": True},
    ],
    "default_sorting_field": "created_at",
}

MESSAGES_SCHEMA = {
    "name": "messages",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "conversation_id", "type": "string"},
        {"name": "user_id", "type": "string", "facet": True},
        {"name": "content", "type": "string"},
        {"name": "created_at", "type": "int64"},
        {"name": "source", "type": "string", "facet": True},
    ],
    "default_sorting_field": "created_at",
}

ZEP_MEMORIES_SCHEMA = {
    "name": "zep_memories",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "user_id", "type": "string", "facet": True},
        {"name": "content", "type": "string"},
        {"name": "memory_type", "type": "string", "optional": True},
        {"name": "created_at", "type": "int64"},
        {"name": "source", "type": "string", "facet": True},
    ],
    "default_sorting_field": "created_at",
}


# =============================================================================
# Client Initialization
# =============================================================================


def get_typesense_client() -> typesense.Client:
    """Get or create Typesense client singleton."""
    global _typesense_client
    if _typesense_client is None:
        if not TYPESENSE_HOST or not TYPESENSE_API_KEY:
            raise RuntimeError(
                "Typesense not configured. Set TYPESENSE_HOST and TYPESENSE_API_KEY."
            )
        _typesense_client = typesense.Client({
            "api_key": TYPESENSE_API_KEY,
            "nodes": [{
                "host": TYPESENSE_HOST,
                "port": TYPESENSE_PORT,
                "protocol": TYPESENSE_PROTOCOL,
            }],
            "connection_timeout_seconds": 5,
        })
    return _typesense_client


def is_typesense_configured() -> bool:
    """Check if Typesense is properly configured."""
    return bool(TYPESENSE_HOST and TYPESENSE_API_KEY and TYPESENSE_SEARCH_ONLY_KEY)


# =============================================================================
# Collection Management
# =============================================================================


def create_collection_if_not_exists(schema: Dict[str, Any]) -> bool:
    """Create a Typesense collection if it doesn't exist.

    Returns:
        True if collection was created, False if it already exists.
    """
    client = get_typesense_client()
    try:
        client.collections[schema["name"]].retrieve()
        logger.info(f"Collection '{schema['name']}' already exists")
        return False
    except ObjectNotFound:
        client.collections.create(schema)
        logger.info(f"Created collection '{schema['name']}'")
        return True


def initialize_collections() -> Dict[str, bool]:
    """Initialize all Typesense collections.

    Returns:
        Dict mapping collection name to whether it was created.
    """
    results = {}
    for schema in [CONVERSATIONS_SCHEMA, MESSAGES_SCHEMA, ZEP_MEMORIES_SCHEMA]:
        results[schema["name"]] = create_collection_if_not_exists(schema)
    return results


def drop_collection(name: str) -> bool:
    """Drop a collection (use with caution)."""
    client = get_typesense_client()
    try:
        client.collections[name].delete()
        logger.info(f"Deleted collection '{name}'")
        return True
    except ObjectNotFound:
        return False


# =============================================================================
# Scoped API Key Generation
# =============================================================================


def generate_scoped_search_key(user_id: str, expires_in_seconds: int = 3600) -> str:
    """Generate a scoped search-only API key filtered by user_id.

    The generated key embeds the user_id filter at the Typesense level,
    preventing users from bypassing authorization even if they modify
    search parameters client-side.

    Args:
        user_id: The WorkOS user ID to scope results to
        expires_in_seconds: Key expiration time (default 1 hour)

    Returns:
        A scoped API key string for client-side use
    """
    if not TYPESENSE_SEARCH_ONLY_KEY:
        raise RuntimeError("TYPESENSE_SEARCH_ONLY_KEY not configured")

    client = get_typesense_client()

    # Create scoped key with embedded filter
    # This filter CANNOT be removed or modified by the client
    # Note: Typesense SDK v29+ uses 'key_parameters' instead of 'parameters'
    # and returns bytes instead of str
    scoped_key = client.keys.generate_scoped_search_key(
        search_key=TYPESENSE_SEARCH_ONLY_KEY,
        key_parameters={
            "filter_by": f"user_id:={user_id}",
            "expires_at": int(time.time()) + expires_in_seconds,
        }
    )

    # SDK returns bytes, convert to string
    if isinstance(scoped_key, bytes):
        scoped_key = scoped_key.decode("utf-8")

    return scoped_key


# =============================================================================
# Indexing Functions
# =============================================================================


def _parse_timestamp(timestamp_str: str) -> int:
    """Convert ISO timestamp string to Unix timestamp."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return int(datetime.now(timezone.utc).timestamp())


def index_conversation(conversation: Dict[str, Any]) -> None:
    """Index a single conversation to Typesense."""
    client = get_typesense_client()

    doc = {
        "id": conversation["id"],
        "user_id": conversation["user_id"],
        "title": conversation.get("title") or "New Conversation",
        "original_query": conversation.get("original_query") or "",
        "created_at": _parse_timestamp(conversation["created_at"]),
        "source": "database",
    }

    client.collections["conversations"].documents.upsert(doc)
    logger.debug(f"Indexed conversation: {conversation['id']}")


def index_message(message: Dict[str, Any], user_id: str) -> None:
    """Index a single message to Typesense."""
    client = get_typesense_client()

    doc = {
        "id": message["id"],
        "conversation_id": message["conversation_id"],
        "user_id": user_id,
        "content": message.get("content") or "",
        "created_at": _parse_timestamp(message["created_at"]),
        "source": "database",
    }

    client.collections["messages"].documents.upsert(doc)
    logger.debug(f"Indexed message: {message['id']}")


def delete_conversation_from_index(conversation_id: str) -> bool:
    """Delete a conversation from the search index."""
    client = get_typesense_client()
    try:
        client.collections["conversations"].documents[conversation_id].delete()
        return True
    except ObjectNotFound:
        return False


def delete_message_from_index(message_id: str) -> bool:
    """Delete a message from the search index."""
    client = get_typesense_client()
    try:
        client.collections["messages"].documents[message_id].delete()
        return True
    except ObjectNotFound:
        return False


def sync_all_conversations() -> Dict[str, int]:
    """Sync all conversations from Supabase to Typesense.

    Returns:
        Dict with 'indexed' count and 'errors' count.
    """
    from .storage import get_supabase_client

    supabase = get_supabase_client()
    client = get_typesense_client()

    # Fetch all conversations
    result = (
        supabase.table("conversations")
        .select("id, user_id, title, original_query, created_at")
        .eq("is_deleted", False)
        .execute()
    )

    indexed = 0
    errors = 0

    for conv in result.data or []:
        try:
            doc = {
                "id": conv["id"],
                "user_id": conv["user_id"],
                "title": conv.get("title") or "New Conversation",
                "original_query": conv.get("original_query") or "",
                "created_at": _parse_timestamp(conv["created_at"]),
                "source": "database",
            }
            client.collections["conversations"].documents.upsert(doc)
            indexed += 1
        except Exception as e:
            logger.error(f"Failed to index conversation {conv['id']}: {e}")
            errors += 1

    logger.info(f"Synced conversations: {indexed} indexed, {errors} errors")
    return {"indexed": indexed, "errors": errors}


def sync_all_messages() -> Dict[str, int]:
    """Sync all messages from Supabase to Typesense.

    Returns:
        Dict with 'indexed' count and 'errors' count.
    """
    from .storage import get_supabase_client

    supabase = get_supabase_client()
    client = get_typesense_client()

    # First, get all conversation -> user_id mappings
    conv_result = (
        supabase.table("conversations")
        .select("id, user_id")
        .eq("is_deleted", False)
        .execute()
    )
    conv_to_user = {c["id"]: c["user_id"] for c in (conv_result.data or [])}

    # Fetch all messages
    msg_result = (
        supabase.table("messages")
        .select("id, conversation_id, content, created_at")
        .execute()
    )

    indexed = 0
    errors = 0

    for msg in msg_result.data or []:
        user_id = conv_to_user.get(msg["conversation_id"])
        if not user_id:
            logger.warning(f"No user_id for message {msg['id']}, skipping")
            errors += 1
            continue

        try:
            doc = {
                "id": msg["id"],
                "conversation_id": msg["conversation_id"],
                "user_id": user_id,
                "content": msg.get("content") or "",
                "created_at": _parse_timestamp(msg["created_at"]),
                "source": "database",
            }
            client.collections["messages"].documents.upsert(doc)
            indexed += 1
        except Exception as e:
            logger.error(f"Failed to index message {msg['id']}: {e}")
            errors += 1

    logger.info(f"Synced messages: {indexed} indexed, {errors} errors")
    return {"indexed": indexed, "errors": errors}


def sync_all() -> Dict[str, Dict[str, int]]:
    """Sync all data from Supabase to Typesense.

    Returns:
        Dict with sync results for each collection.
    """
    return {
        "conversations": sync_all_conversations(),
        "messages": sync_all_messages(),
    }


# =============================================================================
# CLI Interface
# =============================================================================


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python -m backend.search <command>")
        print("Commands:")
        print("  init  - Initialize Typesense collections")
        print("  sync  - Sync all data from Supabase to Typesense")
        print("  drop  - Drop all collections (use with caution)")
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        print("Initializing Typesense collections...")
        results = initialize_collections()
        for name, created in results.items():
            status = "created" if created else "already exists"
            print(f"  {name}: {status}")
        print("Done!")

    elif command == "sync":
        print("Syncing data to Typesense...")
        results = sync_all()
        for collection, stats in results.items():
            print(f"  {collection}: {stats['indexed']} indexed, {stats['errors']} errors")
        print("Done!")

    elif command == "drop":
        print("Dropping all collections...")
        for name in ["conversations", "messages", "zep_memories"]:
            if drop_collection(name):
                print(f"  Dropped: {name}")
            else:
                print(f"  Not found: {name}")
        print("Done!")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

