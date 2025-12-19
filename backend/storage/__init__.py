"""Supabase-backed storage for conversations.

This package provides user-scoped conversation storage using Supabase PostgreSQL.
It maintains backward compatibility with the previous single-file API.

Database Schema:
- conversations: id, user_id, organization_id, title, original_query, improved_query, timestamps
- messages: id, conversation_id, content (user queries only)
- assistant_responses: id, user_message_id (FK), stage1/2/3 data, timing metrics
- conversation_shares: For future collaboration features

The FK design provides:
- Explicit 1:1 relationship between user messages and assistant responses
- Data integrity via foreign key constraints with CASCADE delete
- Clean separation of user queries from AI responses

Search Integration:
- All CRUD operations automatically sync to Typesense for full-text search
- Indexing is done asynchronously to not block the main request

Repository Pattern:
- Abstract base classes in base.py define the storage interface
- Supabase implementations in conversations.py, messages.py, responses.py
- Allows swapping storage backends without changing application code
"""

# Re-export abstract base classes
from .base import ConversationRepository, MessageRepository, ResponseRepository

# Re-export all public functions for backward compatibility
from .client import get_supabase_client

from .conversations import (
    create_conversation,
    get_conversation,
    list_conversations,
    update_conversation_title,
    update_conversation_queries,
    _verify_conversation_ownership,
    STALE_DELIBERATION_TIMEOUT_MINUTES,
)

from .messages import add_user_message

from .responses import (
    add_assistant_response,
    create_response_placeholder,
    delete_response_placeholder,
    update_response_stage1,
    update_response_stage2,
    update_response_stage3,
    update_response_status,
    set_response_error,
    save_model_response,
    get_partial_stage_responses,
    get_response_with_partial_stages,
    cleanup_partial_stage_responses,
    get_incomplete_responses_for_conversation,
)

__all__ = [
    # Abstract base classes (repository pattern)
    "ConversationRepository",
    "MessageRepository",
    "ResponseRepository",
    # Client
    "get_supabase_client",
    # Conversations
    "create_conversation",
    "get_conversation",
    "list_conversations",
    "update_conversation_title",
    "update_conversation_queries",
    "_verify_conversation_ownership",
    "STALE_DELIBERATION_TIMEOUT_MINUTES",
    # Messages
    "add_user_message",
    # Responses
    "add_assistant_response",
    "create_response_placeholder",
    "delete_response_placeholder",
    "update_response_stage1",
    "update_response_stage2",
    "update_response_stage3",
    "update_response_status",
    "set_response_error",
    "save_model_response",
    "get_partial_stage_responses",
    "get_response_with_partial_stages",
    "cleanup_partial_stage_responses",
    "get_incomplete_responses_for_conversation",
]

