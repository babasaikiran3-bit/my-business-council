"""SQLite storage backend implementation."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import create_engine, func, or_, text
from sqlalchemy.orm import sessionmaker, Session
from .base import StorageBackend
from .models import (
    Base,
    Conversation,
    Message,
    FTS_TABLE_SQL,
    FTS_TRIGGER_INSERT_SQL,
    FTS_TRIGGER_UPDATE_SQL,
    FTS_TRIGGER_DELETE_SQL,
)


class SQLiteStorageBackend(StorageBackend):
    """SQLite database storage implementation with full-text search."""

    def __init__(self, db_path: str = "data/conversations.db"):
        """
        Initialize SQLite storage backend.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Create tables
        Base.metadata.create_all(self.engine)

        # Set up full-text search
        self._setup_fts()

    def _setup_fts(self):
        """Set up full-text search tables and triggers."""
        with self.engine.connect() as conn:
            conn.execute(text(FTS_TABLE_SQL))
            conn.execute(text(FTS_TRIGGER_INSERT_SQL))
            conn.execute(text(FTS_TRIGGER_UPDATE_SQL))
            conn.execute(text(FTS_TRIGGER_DELETE_SQL))
            conn.commit()

    def _get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def create_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Create a new conversation."""
        session = self._get_session()
        try:
            conversation = Conversation(
                id=conversation_id,
                created_at=datetime.utcnow(),
                title="New Conversation"
            )
            session.add(conversation)
            session.commit()
            return conversation.to_dict(include_messages=True)
        finally:
            session.close()

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation by ID."""
        session = self._get_session()
        try:
            conversation = session.query(Conversation).filter_by(id=conversation_id).first()
            if conversation is None:
                return None
            return conversation.to_dict(include_messages=True)
        finally:
            session.close()

    def list_conversations(self) -> List[Dict[str, Any]]:
        """List all conversations (metadata only)."""
        session = self._get_session()
        try:
            conversations = session.query(Conversation).order_by(
                Conversation.created_at.desc()
            ).all()
            return [conv.to_dict(include_messages=False) for conv in conversations]
        finally:
            session.close()

    def add_user_message(self, conversation_id: str, content: str) -> None:
        """Add a user message to a conversation."""
        session = self._get_session()
        try:
            # Verify conversation exists
            conversation = session.query(Conversation).filter_by(id=conversation_id).first()
            if conversation is None:
                raise ValueError(f"Conversation {conversation_id} not found")

            message = Message(
                conversation_id=conversation_id,
                role="user",
                content=content,
                created_at=datetime.utcnow()
            )
            session.add(message)
            session.commit()
        finally:
            session.close()

    def add_assistant_message(
        self,
        conversation_id: str,
        stage1_results: List[Dict[str, Any]],
        stage2_results: List[Dict[str, Any]],
        stage3_result: Dict[str, Any]
    ) -> None:
        """Add an assistant message with all council stages."""
        session = self._get_session()
        try:
            # Verify conversation exists
            conversation = session.query(Conversation).filter_by(id=conversation_id).first()
            if conversation is None:
                raise ValueError(f"Conversation {conversation_id} not found")

            # Calculate costs from each stage
            stage1_cost = sum(r.get('cost_usd', 0.0) for r in stage1_results)
            stage2_cost = sum(r.get('cost_usd', 0.0) for r in stage2_results)
            stage3_cost = stage3_result.get('cost_usd', 0.0)

            message = Message(
                conversation_id=conversation_id,
                role="assistant",
                stage1=stage1_results,
                stage2=stage2_results,
                stage3=stage3_result,
                stage1_cost=stage1_cost,
                stage2_cost=stage2_cost,
                stage3_cost=stage3_cost,
                created_at=datetime.utcnow()
            )
            session.add(message)
            session.commit()
        finally:
            session.close()

    def update_conversation_title(self, conversation_id: str, title: str) -> None:
        """Update the title of a conversation."""
        session = self._get_session()
        try:
            conversation = session.query(Conversation).filter_by(id=conversation_id).first()
            if conversation is None:
                raise ValueError(f"Conversation {conversation_id} not found")

            conversation.title = title
            session.commit()
        finally:
            session.close()

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        session = self._get_session()
        try:
            conversation = session.query(Conversation).filter_by(id=conversation_id).first()
            if conversation is None:
                return False

            session.delete(conversation)
            session.commit()
            return True
        finally:
            session.close()

    def search_conversations(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search conversations using full-text search.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching conversation metadata
        """
        session = self._get_session()
        try:
            # Use FTS5 for full-text search
            # Search in message content
            fts_query = text("""
                SELECT DISTINCT c.id, c.created_at, c.title, COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.id IN (
                    SELECT conversation_id FROM messages_fts
                    WHERE messages_fts MATCH :query
                )
                OR c.title LIKE :title_pattern
                GROUP BY c.id
                ORDER BY c.created_at DESC
                LIMIT :limit
            """)

            results = session.execute(
                fts_query,
                {
                    "query": query,
                    "title_pattern": f"%{query}%",
                    "limit": limit
                }
            ).fetchall()

            return [
                {
                    "id": row[0],
                    "created_at": row[1].isoformat() if isinstance(row[1], datetime) else row[1],
                    "title": row[2],
                    "message_count": row[3]
                }
                for row in results
            ]
        finally:
            session.close()

    def get_conversation_costs(self, conversation_id: str) -> Dict[str, float]:
        """Get cost statistics for a conversation."""
        session = self._get_session()
        try:
            # Sum up costs from all messages
            result = session.query(
                func.sum(Message.stage1_cost).label('stage1_total'),
                func.sum(Message.stage2_cost).label('stage2_total'),
                func.sum(Message.stage3_cost).label('stage3_total')
            ).filter(Message.conversation_id == conversation_id).first()

            stage1_usd = result.stage1_total or 0.0
            stage2_usd = result.stage2_total or 0.0
            stage3_usd = result.stage3_total or 0.0
            total_usd = stage1_usd + stage2_usd + stage3_usd

            return {
                "total_usd": round(total_usd, 6),
                "stage1_usd": round(stage1_usd, 6),
                "stage2_usd": round(stage2_usd, 6),
                "stage3_usd": round(stage3_usd, 6)
            }
        finally:
            session.close()

    def get_total_costs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get total costs across all conversations."""
        session = self._get_session()
        try:
            query = session.query(
                func.count(func.distinct(Message.conversation_id)).label('conversation_count'),
                func.sum(Message.stage1_cost).label('stage1_total'),
                func.sum(Message.stage2_cost).label('stage2_total'),
                func.sum(Message.stage3_cost).label('stage3_total')
            )

            # Apply date filters if provided
            if start_date:
                query = query.filter(Message.created_at >= start_date)
            if end_date:
                query = query.filter(Message.created_at <= end_date)

            result = query.first()

            conversation_count = result.conversation_count or 0
            stage1_usd = result.stage1_total or 0.0
            stage2_usd = result.stage2_total or 0.0
            stage3_usd = result.stage3_total or 0.0
            total_usd = stage1_usd + stage2_usd + stage3_usd

            return {
                "total_usd": round(total_usd, 6),
                "conversation_count": conversation_count,
                "stage1_usd": round(stage1_usd, 6),
                "stage2_usd": round(stage2_usd, 6),
                "stage3_usd": round(stage3_usd, 6)
            }
        finally:
            session.close()
