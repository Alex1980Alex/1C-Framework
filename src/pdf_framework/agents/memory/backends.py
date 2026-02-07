"""Backends for conversation memory storage (Phase 9).

Provides:
- MemoryBackend: In-memory storage for dev/testing
- SQLiteBackend: Persistent SQLite storage for production
"""

import aiosqlite
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Literal

from src.pdf_framework.agents.memory.conversation import Message

logger = logging.getLogger(__name__)


class BaseBackend(ABC):
    """Abstract base class for conversation backends."""

    @abstractmethod
    async def get_messages(self, thread_id: str) -> list[Message]:
        """Get all messages for a thread."""
        pass

    @abstractmethod
    async def add_message(self, thread_id: str, message: Message) -> None:
        """Add a message to a thread."""
        pass

    @abstractmethod
    async def clear_thread(self, thread_id: str) -> None:
        """Clear all messages from a thread."""
        pass

    @abstractmethod
    async def list_threads(self, limit: int) -> list[dict]:
        """List all threads with metadata."""
        pass

    @abstractmethod
    async def cleanup_old_threads(self, days: int) -> int:
        """Delete threads older than N days."""
        pass


class MemoryBackend(BaseBackend):
    """In-memory backend for conversation storage.

    Simple dict-based storage, not persistent across restarts.
    Useful for development and testing.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._storage: dict[str, list[Message]] = {}

    async def get_messages(self, thread_id: str) -> list[Message]:
        """Get all messages for a thread."""
        return self._storage.get(thread_id, []).copy()

    async def add_message(self, thread_id: str, message: Message) -> None:
        """Add a message to a thread."""
        if thread_id not in self._storage:
            self._storage[thread_id] = []

        self._storage[thread_id].append(message)

    async def clear_thread(self, thread_id: str) -> None:
        """Clear all messages from a thread."""
        if thread_id in self._storage:
            del self._storage[thread_id]

    async def list_threads(self, limit: int) -> list[dict]:
        """List all threads with metadata."""
        result = []

        for thread_id, messages in list(self._storage.items())[:limit]:
            if messages:
                result.append({
                    "thread_id": thread_id,
                    "message_count": len(messages),
                    "last_updated": messages[-1].timestamp.isoformat(),
                })

        # Sort by last updated (newest first)
        result.sort(key=lambda x: x["last_updated"], reverse=True)

        return result

    async def cleanup_old_threads(self, days: int) -> int:
        """Delete threads older than N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        to_delete = []

        for thread_id, messages in self._storage.items():
            if messages and messages[-1].timestamp < cutoff:
                to_delete.append(thread_id)

        for thread_id in to_delete:
            del self._storage[thread_id]

        return len(to_delete)


class SQLiteBackend(BaseBackend):
    """Persistent SQLite backend for conversation storage.

    Stores messages in SQLite database with schema:
    - threads: thread_id, created_at, updated_at
    - messages: id, thread_id, role, content, timestamp, metadata_json
    """

    def __init__(self, db_path: str):
        """
        Initialize SQLite backend.

        Args:
            db_path: Path to SQLite database file
        """
        self._db_path = db_path
        self._initialized = False

    async def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
        if self._initialized:
            return

        async with aiosqlite.connect(self._db_path) as db:
            # Threads table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Messages table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE
                )
            """)

            # Indexes for faster queries
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_thread
                ON messages(thread_id, id)
            """)

            await db.commit()

        self._initialized = True

    async def get_messages(self, thread_id: str) -> list[Message]:
        """Get all messages for a thread, ordered by id."""
        await self._ensure_tables()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """
                SELECT role, content, timestamp, metadata
                FROM messages
                WHERE thread_id = ?
                ORDER BY id ASC
                """,
                (thread_id,)
            )

            rows = await cursor.fetchall()

            messages = []
            for row in rows:
                import json
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                messages.append(Message(
                    role=row["role"],
                    content=row["content"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    metadata=metadata,
                ))

            return messages

    async def add_message(self, thread_id: str, message: Message) -> None:
        """Add a message to a thread."""
        await self._ensure_tables()

        import json

        async with aiosqlite.connect(self._db_path) as db:
            # Ensure thread exists
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                """
                INSERT OR IGNORE INTO threads (thread_id, created_at, updated_at)
                VALUES (?, ?, ?)
                """,
                (thread_id, now, now)
            )

            # Update thread timestamp
            await db.execute(
                """
                UPDATE threads SET updated_at = ? WHERE thread_id = ?
                """,
                (now, thread_id)
            )

            # Insert message
            await db.execute(
                """
                INSERT INTO messages (thread_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    thread_id,
                    message.role,
                    message.content,
                    message.timestamp.isoformat(),
                    json.dumps(message.metadata),
                )
            )

            await db.commit()

    async def clear_thread(self, thread_id: str) -> None:
        """Clear all messages from a thread and delete the thread."""
        await self._ensure_tables()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
            await db.execute("DELETE FROM threads WHERE thread_id = ?", (thread_id,))
            await db.commit()

    async def list_threads(self, limit: int) -> list[dict]:
        """List all threads with metadata."""
        await self._ensure_tables()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """
                SELECT
                    t.thread_id,
                    t.updated_at,
                    COUNT(m.id) as message_count
                FROM threads t
                LEFT JOIN messages m ON t.thread_id = m.thread_id
                GROUP BY t.thread_id
                ORDER BY t.updated_at DESC
                LIMIT ?
                """,
                (limit,)
            )

            rows = await cursor.fetchall()

            return [
                {
                    "thread_id": row["thread_id"],
                    "message_count": row["message_count"],
                    "last_updated": row["updated_at"],
                }
                for row in rows
            ]

    async def cleanup_old_threads(self, days: int) -> int:
        """Delete threads older than N days."""
        await self._ensure_tables()

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT thread_id FROM threads
                WHERE updated_at < ?
                """,
                (cutoff.isoformat(),)
            )

            rows = await cursor.fetchall()
            thread_ids = [row[0] for row in rows]

            for thread_id in thread_ids:
                await self.clear_thread(thread_id)

            return len(thread_ids)
