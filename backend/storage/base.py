"""Abstract base classes for storage repositories.

This module defines the repository pattern interfaces for data access,
allowing the application to work with different storage backends
(Supabase, PostgreSQL, in-memory, etc.) without changing the core logic.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class ConversationRepository(ABC):
    """Abstract repository for conversation operations.
    
    This interface defines the contract for conversation storage,
    allowing different implementations (Supabase, PostgreSQL, etc.).
    """
    
    @abstractmethod
    def create(
        self,
        user_id: str,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new conversation.
        
        Args:
            user_id: The ID of the user creating the conversation.
            organization_id: Optional organization ID for multi-tenant support.
            
        Returns:
            The created conversation dict with id, title, created_at, etc.
        """
        pass
    
    @abstractmethod
    def get(
        self,
        conversation_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a conversation by ID.
        
        Args:
            conversation_id: The conversation ID.
            user_id: The user ID (for access control).
            
        Returns:
            The conversation dict with messages, or None if not found.
        """
        pass
    
    @abstractmethod
    def list(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List conversations for a user.
        
        Args:
            user_id: The user ID.
            limit: Maximum number of conversations to return.
            offset: Number of conversations to skip.
            
        Returns:
            Tuple of (conversations list, total count).
        """
        pass
    
    @abstractmethod
    def update_title(
        self,
        conversation_id: str,
        user_id: str,
        title: str,
    ) -> bool:
        """Update a conversation's title.
        
        Args:
            conversation_id: The conversation ID.
            user_id: The user ID (for access control).
            title: The new title.
            
        Returns:
            True if updated, False if not found.
        """
        pass
    
    @abstractmethod
    def update_queries(
        self,
        conversation_id: str,
        user_id: str,
        original_query: str,
        improved_query: Optional[str] = None,
    ) -> bool:
        """Update a conversation's query fields.
        
        Args:
            conversation_id: The conversation ID.
            user_id: The user ID (for access control).
            original_query: The original user query.
            improved_query: Optional improved version of the query.
            
        Returns:
            True if updated, False if not found.
        """
        pass


class MessageRepository(ABC):
    """Abstract repository for message operations."""
    
    @abstractmethod
    def add_user_message(
        self,
        conversation_id: str,
        user_id: str,
        content: str,
    ) -> str:
        """Add a user message to a conversation.
        
        Args:
            conversation_id: The conversation ID.
            user_id: The user ID.
            content: The message content.
            
        Returns:
            The created message ID.
        """
        pass


class ResponseRepository(ABC):
    """Abstract repository for assistant response operations."""
    
    @abstractmethod
    def create_placeholder(self, user_message_id: str) -> str:
        """Create a placeholder response for incremental updates.
        
        Args:
            user_message_id: The user message ID this response is for.
            
        Returns:
            The created response ID.
        """
        pass
    
    @abstractmethod
    def update_status(self, response_id: str, status: str) -> bool:
        """Update a response's status.
        
        Args:
            response_id: The response ID.
            status: The new status.
            
        Returns:
            True if updated, False if not found.
        """
        pass

