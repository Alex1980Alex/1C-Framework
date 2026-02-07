"""Conversation memory for multi-turn dialog support.

Author: Claude Code
Version: 1.0.0 - Phase 9.1: Conversation Memory
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Message(BaseModel):
    """Single message in conversation history."""

    role: Literal["user", "assistant"] = Field(
        description="Message sender role"
    )
    content: str = Field(
        description="Message text content"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the message was created"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Optional metadata (strategy, sources, latency, etc.)"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ConversationMemory:
    """
    Manages conversation history with configurable backend.

    Supports:
    - Thread-based conversation isolation
    - Context window management (limit recent messages)
    - Persistent storage via SQLite
    - Auto-cleanup of old threads
    """

    def __init__(
        self,
        backend: Literal["memory", "sqlite"] = "sqlite",
        db_path: str = "data/conversations.db",
        max_history: int = 10,
        auto_cleanup_days: int = 30,
    ):
        """
        Initialize conversation memory.

        Args:
            backend: Storage backend ("memory" or "sqlite")
            db_path: Path to SQLite database (for sqlite backend)
            max_history: Maximum messages to return per thread
            auto_cleanup_days: Days before auto-cleaning old threads (0 = disabled)
        """
        self._max_history = max_history
        self._auto_cleanup_days = auto_cleanup_days

        # Initialize backend (lazy import to avoid circular dependency)
        from src.pdf_framework.agents.memory.backends import MemoryBackend, SQLiteBackend

        if backend == "sqlite":
            self._backend = SQLiteBackend(db_path)
        else:
            self._backend = MemoryBackend()

        logger.info(
            f"[MEMORY] Initialized with {backend} backend, "
            f"max_history={max_history}, auto_cleanup={auto_cleanup_days} days"
        )

    async def get_history(
        self,
        thread_id: str,
        limit: int | None = None,
    ) -> list[Message]:
        """
        Get conversation history for a thread.

        Args:
            thread_id: Thread identifier
            limit: Maximum messages to return (default: max_history)

        Returns:
            List of messages, oldest to newest
        """
        limit = limit or self._max_history

        messages = await self._backend.get_messages(thread_id)

        # Return last N messages
        result = messages[-limit:] if len(messages) > limit else messages

        logger.debug(f"[MEMORY] Retrieved {len(result)} messages for thread {thread_id}")

        return result

    async def add_message(
        self,
        thread_id: str,
        role: Literal["user", "assistant"],
        content: str,
        metadata: dict | None = None,
    ) -> Message:
        """
        Add a message to conversation history.

        Args:
            thread_id: Thread identifier
            role: Message sender role
            content: Message text
            metadata: Optional metadata (strategy, sources, etc.)

        Returns:
            Created message
        """
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
        )

        await self._backend.add_message(thread_id, message)

        logger.debug(f"[MEMORY] Added {role} message to thread {thread_id}")

        return message

    async def clear_thread(self, thread_id: str) -> None:
        """
        Clear all messages from a thread.

        Args:
            thread_id: Thread identifier
        """
        await self._backend.clear_thread(thread_id)

        logger.info(f"[MEMORY] Cleared thread {thread_id}")

    async def list_threads(
        self,
        limit: int = 100,
    ) -> list[dict]:
        """
        List all active threads.

        Args:
            limit: Maximum threads to return

        Returns:
            List of thread info dicts with keys: thread_id, message_count, last_updated
        """
        threads = await self._backend.list_threads(limit)

        logger.debug(f"[MEMORY] Listed {len(threads)} threads")

        return threads

    async def cleanup_old_threads(self, days: int | None = None) -> int:
        """
        Delete threads older than specified days.

        Args:
            days: Days threshold (default: auto_cleanup_days from init)

        Returns:
            Number of threads deleted
        """
        days = days or self._auto_cleanup_days

        if days == 0:
            logger.debug("[MEMORY] Auto-cleanup disabled (days=0)")
            return 0

        count = await self._backend.cleanup_old_threads(days)

        if count > 0:
            logger.info(f"[MEMORY] Cleaned up {count} threads older than {days} days")

        return count

    async def get_thread_stats(self, thread_id: str) -> dict:
        """
        Get statistics for a thread.

        Args:
            thread_id: Thread identifier

        Returns:
            Dict with message_count, first_message, last_message
        """
        messages = await self._backend.get_messages(thread_id)

        if not messages:
            return {
                "message_count": 0,
                "first_message": None,
                "last_message": None,
            }

        return {
            "message_count": len(messages),
            "first_message": messages[0].timestamp.isoformat(),
            "last_message": messages[-1].timestamp.isoformat(),
        }
