"""SQLite database setup with SQLAlchemy."""

import os
import json
from datetime import datetime
from typing import Any, List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON

from .config import DATA_DIR

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Database URL
# Database URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(DATA_DIR, 'council.db')}"

# SQLAlchemy setup
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()


class ConversationModel(Base):
    """Conversation database model."""
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # We could establish a relationship here, but for simplicity in this
    # refactor phase, we'll just query messages by conversation_id manually
    # or add the relationship if needed later on.


class MessageModel(Base):
    """Message database model."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, index=True)
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text) # For user messages, simple text. For assistant, JSON string.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Metadata fields to store stage results as JSON
    stage1_results = Column(JSON, nullable=True)
    stage2_results = Column(JSON, nullable=True)
    stage3_result = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)


async def init_db():
    """Initialize the database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency for getting DB session."""
    async with AsyncSessionLocal() as session:
        yield session
