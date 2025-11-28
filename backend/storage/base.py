"""Abstract base class for storage backends."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class StorageBackend(ABC):
    """Abstract interface for conversation storage backends."""

    @abstractmethod
    def create_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Create a new conversation.

        Args:
            conversation_id: Unique identifier for the conversation

        Returns:
            Dict with conversation metadata
        """
        pass

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: The conversation ID to retrieve

        Returns:
            Conversation dict or None if not found
        """
        pass

    @abstractmethod
    def list_conversations(self) -> List[Dict[str, Any]]:
        """
        List all conversations (metadata only).

        Returns:
            List of conversation metadata dicts
        """
        pass

    @abstractmethod
    def add_user_message(self, conversation_id: str, content: str) -> None:
        """
        Add a user message to a conversation.

        Args:
            conversation_id: The conversation ID
            content: The message content
        """
        pass

    @abstractmethod
    def add_assistant_message(
        self,
        conversation_id: str,
        stage1_results: List[Dict[str, Any]],
        stage2_results: List[Dict[str, Any]],
        stage3_result: Dict[str, Any]
    ) -> None:
        """
        Add an assistant message with all council stages.

        Args:
            conversation_id: The conversation ID
            stage1_results: Stage 1 individual responses
            stage2_results: Stage 2 peer rankings
            stage3_result: Stage 3 final synthesis
        """
        pass

    @abstractmethod
    def update_conversation_title(self, conversation_id: str, title: str) -> None:
        """
        Update the title of a conversation.

        Args:
            conversation_id: The conversation ID
            title: New title
        """
        pass

    @abstractmethod
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def search_conversations(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search conversations by content.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching conversation metadata
        """
        pass

    @abstractmethod
    def get_conversation_costs(self, conversation_id: str) -> Dict[str, float]:
        """
        Get cost statistics for a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            Dict with cost breakdown (total_usd, stage1_usd, stage2_usd, stage3_usd)
        """
        pass

    @abstractmethod
    def get_total_costs(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get total costs across all conversations.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dict with total costs and breakdown
        """
        pass
