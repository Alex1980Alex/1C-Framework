"""Tests for SQLite backend (Phase 9.1).

Tests persistent storage with real SQLite database (temp file).
"""

import os
import tempfile

import pytest
from datetime import datetime, timezone, timedelta

from src.pdf_framework.agents.memory.conversation import Message
from src.pdf_framework.agents.memory.backends import SQLiteBackend


@pytest.fixture
def db_path():
    """Create a temp database path and cleanup after test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # Remove so SQLite can create it
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestSQLiteBackend:
    """Test SQLite persistent backend."""

    @pytest.mark.asyncio
    async def test_creates_tables(self, db_path):
        backend = SQLiteBackend(db_path)
        await backend._ensure_tables()
        assert backend._initialized is True
        assert os.path.exists(db_path)

    @pytest.mark.asyncio
    async def test_double_init_is_safe(self, db_path):
        backend = SQLiteBackend(db_path)
        await backend._ensure_tables()
        await backend._ensure_tables()  # Should not fail
        assert backend._initialized is True

    @pytest.mark.asyncio
    async def test_add_and_get_messages(self, db_path):
        backend = SQLiteBackend(db_path)
        msg = Message(role="user", content="Hello from SQLite")
        await backend.add_message("t1", msg)

        messages = await backend.get_messages("t1")
        assert len(messages) == 1
        assert messages[0].content == "Hello from SQLite"
        assert messages[0].role == "user"

    @pytest.mark.asyncio
    async def test_messages_ordered_by_id(self, db_path):
        backend = SQLiteBackend(db_path)
        await backend.add_message("t1", Message(role="user", content="First"))
        await backend.add_message("t1", Message(role="assistant", content="Second"))
        await backend.add_message("t1", Message(role="user", content="Third"))

        messages = await backend.get_messages("t1")
        assert len(messages) == 3
        assert messages[0].content == "First"
        assert messages[2].content == "Third"

    @pytest.mark.asyncio
    async def test_thread_isolation(self, db_path):
        backend = SQLiteBackend(db_path)
        await backend.add_message("t1", Message(role="user", content="Thread 1"))
        await backend.add_message("t2", Message(role="user", content="Thread 2"))

        t1 = await backend.get_messages("t1")
        t2 = await backend.get_messages("t2")
        assert t1[0].content == "Thread 1"
        assert t2[0].content == "Thread 2"

    @pytest.mark.asyncio
    async def test_clear_thread(self, db_path):
        backend = SQLiteBackend(db_path)
        await backend.add_message("t1", Message(role="user", content="Hello"))
        await backend.clear_thread("t1")

        messages = await backend.get_messages("t1")
        assert messages == []

    @pytest.mark.asyncio
    async def test_list_threads(self, db_path):
        backend = SQLiteBackend(db_path)
        await backend.add_message("t1", Message(role="user", content="A"))
        await backend.add_message("t2", Message(role="user", content="B"))

        threads = await backend.list_threads(100)
        assert len(threads) == 2
        thread_ids = {t["thread_id"] for t in threads}
        assert "t1" in thread_ids
        assert "t2" in thread_ids

    @pytest.mark.asyncio
    async def test_list_threads_message_count(self, db_path):
        backend = SQLiteBackend(db_path)
        await backend.add_message("t1", Message(role="user", content="A"))
        await backend.add_message("t1", Message(role="assistant", content="B"))

        threads = await backend.list_threads(100)
        assert threads[0]["message_count"] == 2

    @pytest.mark.asyncio
    async def test_metadata_preserved(self, db_path):
        backend = SQLiteBackend(db_path)
        msg = Message(
            role="assistant",
            content="Answer",
            metadata={"strategy": "hybrid", "score": 0.95},
        )
        await backend.add_message("t1", msg)

        messages = await backend.get_messages("t1")
        assert messages[0].metadata["strategy"] == "hybrid"
        assert messages[0].metadata["score"] == 0.95

    @pytest.mark.asyncio
    async def test_timestamp_preserved(self, db_path):
        backend = SQLiteBackend(db_path)
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        msg = Message(role="user", content="Test", timestamp=ts)
        await backend.add_message("t1", msg)

        messages = await backend.get_messages("t1")
        assert messages[0].timestamp.year == 2025
        assert messages[0].timestamp.month == 1
        assert messages[0].timestamp.day == 15

    @pytest.mark.asyncio
    async def test_cleanup_old_threads(self, db_path):
        backend = SQLiteBackend(db_path)

        # Add thread that will be "old" based on threads.updated_at
        await backend.add_message("old_thread", Message(role="user", content="Old"))

        # Manually set updated_at to old date
        import aiosqlite
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE threads SET updated_at = ? WHERE thread_id = ?",
                (old_date, "old_thread"),
            )
            await db.commit()

        # Add recent thread
        await backend.add_message("new_thread", Message(role="user", content="New"))

        # Cleanup
        deleted = await backend.cleanup_old_threads(30)
        assert deleted == 1

        # Old thread gone, new thread remains
        assert await backend.get_messages("old_thread") == []
        assert len(await backend.get_messages("new_thread")) == 1

    @pytest.mark.asyncio
    async def test_persistence_across_instances(self, db_path):
        """Data persists across different backend instances."""
        backend1 = SQLiteBackend(db_path)
        await backend1.add_message("t1", Message(role="user", content="Persistent"))

        # Create new instance pointing to same DB
        backend2 = SQLiteBackend(db_path)
        messages = await backend2.get_messages("t1")
        assert len(messages) == 1
        assert messages[0].content == "Persistent"
