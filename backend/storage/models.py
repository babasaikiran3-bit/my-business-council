"""SQLAlchemy models for conversation storage."""

from sqlalchemy import Column, String, DateTime, Integer, Float, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class Conversation(Base):
    """Conversation model."""

    __tablename__ = 'conversations'

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    title = Column(String, nullable=False, default="New Conversation")

    # Relationship to messages
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    # Indexes for common queries
    __table_args__ = (
        Index('idx_created_at_desc', created_at.desc()),
    )

    def to_dict(self, include_messages=True):
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "title": self.title,
        }
        if include_messages:
            result["messages"] = [msg.to_dict() for msg in self.messages]
        else:
            result["message_count"] = len(self.messages)
        return result


class Message(Base):
    """Message model."""

    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey('conversations.id'), nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # User message fields
    content = Column(Text, nullable=True)  # For user messages

    # Assistant message fields (council stages)
    stage1 = Column(JSON, nullable=True)  # List of individual responses
    stage2 = Column(JSON, nullable=True)  # List of rankings
    stage3 = Column(JSON, nullable=True)  # Final synthesis

    # Cost tracking
    stage1_cost = Column(Float, default=0.0)
    stage2_cost = Column(Float, default=0.0)
    stage3_cost = Column(Float, default=0.0)

    # Relationship
    conversation = relationship("Conversation", back_populates="messages")

    # Indexes
    __table_args__ = (
        Index('idx_conversation_created', conversation_id, created_at),
    )

    def to_dict(self):
        """Convert to dictionary."""
        if self.role == "user":
            return {
                "role": "user",
                "content": self.content
            }
        else:  # assistant
            return {
                "role": "assistant",
                "stage1": self.stage1,
                "stage2": self.stage2,
                "stage3": self.stage3
            }

    @property
    def total_cost(self):
        """Calculate total cost for this message."""
        return (self.stage1_cost or 0.0) + (self.stage2_cost or 0.0) + (self.stage3_cost or 0.0)


class Repository(Base):
    """GitHub repository metadata."""

    __tablename__ = 'repositories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False, unique=True, index=True)  # e.g., "owner/repo"
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String, nullable=True)
    default_branch = Column(String, nullable=False, default="main")

    # Cached metadata
    stars = Column(Integer, default=0)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Cached content (JSON structure and key files)
    tree_structure = Column(JSON, nullable=True)  # Directory tree
    key_files = Column(JSON, nullable=True)  # {filename: content}
    summary = Column(Text, nullable=True)  # Generated summary

    # Relationships
    conversation_repos = relationship("ConversationRepository", back_populates="repository", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "name": self.name,
            "description": self.description,
            "language": self.language,
            "default_branch": self.default_branch,
            "stars": self.stars,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class ConversationRepository(Base):
    """Many-to-many relationship between conversations and repositories."""

    __tablename__ = 'conversation_repositories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey('conversations.id'), nullable=False, index=True)
    repository_id = Column(Integer, ForeignKey('repositories.id'), nullable=False, index=True)
    attached_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation")
    repository = relationship("Repository", back_populates="conversation_repos")

    # Unique constraint: each repo can only be attached once per conversation
    __table_args__ = (
        Index('idx_conv_repo_unique', conversation_id, repository_id, unique=True),
    )


# Update Conversation model to include repository relationship
Conversation.repositories = relationship(
    "Repository",
    secondary="conversation_repositories",
    viewonly=True
)


class File(Base):
    """Uploaded file attached to a conversation."""

    __tablename__ = 'files'

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey('conversations.id'), nullable=False, index=True)
    filename = Column(String, nullable=False)
    content = Column(Text, nullable=False)  # File contents as text
    mime_type = Column(String, nullable=True)  # e.g., "text/plain", "application/json"
    size_bytes = Column(Integer, nullable=False)  # Original file size
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    conversation = relationship("Conversation")

    # Index for efficient queries
    __table_args__ = (
        Index('idx_conversation_files', conversation_id, uploaded_at),
    )

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


# Update Conversation model to include files relationship
Conversation.files = relationship("File", back_populates="conversation", cascade="all, delete-orphan")
File.conversation = relationship("Conversation", back_populates="files")


# Virtual table for full-text search
# Note: This will be created with raw SQL as SQLAlchemy doesn't directly support FTS5
FTS_TABLE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    message_id UNINDEXED,
    conversation_id UNINDEXED,
    content,
    tokenize = 'porter unicode61'
);
"""

FTS_TRIGGER_INSERT_SQL = """
CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages
WHEN new.role = 'user'
BEGIN
    INSERT INTO messages_fts(message_id, conversation_id, content)
    VALUES (new.id, new.conversation_id, new.content);
END;
"""

FTS_TRIGGER_UPDATE_SQL = """
CREATE TRIGGER IF NOT EXISTS messages_fts_update AFTER UPDATE ON messages
WHEN new.role = 'user'
BEGIN
    UPDATE messages_fts SET content = new.content
    WHERE message_id = new.id;
END;
"""

FTS_TRIGGER_DELETE_SQL = """
CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages
BEGIN
    DELETE FROM messages_fts WHERE message_id = old.id;
END;
"""
