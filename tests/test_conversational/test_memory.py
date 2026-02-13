"""Tests for Conversation Memory and MemoryBackend (Phase 9.1).

Tests Message model, MemoryBackend, and ConversationMemory without SQLite.
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.pdf_framework.agents.memory.conversation import Message, ConversationMemory
from src.pdf_framework.agents.memory.backends import MemoryBackend


class TestMessage:
    """Test Message Pydantic model."""

    def test_creates_with_defaults(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.metadata == {}
        assert msg.timestamp is not None

    def test_creates_with_metadata(self):
        msg = Message(
            role="assistant",
            content="Answer",
            metadata={"strategy": "hybrid", "sources": ["doc1"]},
        )
        assert msg.metadata["strategy"] == "hybrid"

    def test_to_dict(self):
        msg = Message(role="user", content="Test")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Test"
        assert "timestamp" in d
        assert isinstance(d["timestamp"], str)  # ISO format string

    def test_timestamp_is_utc(self):
        msg = Message(role="user", content="Test")
        assert msg.timestamp.tzinfo is not None


class TestMemoryBackend:
    """Test in-memory backend."""

    @pytest.mark.asyncio
    async def test_add_and_get_messages(self):
        backend = MemoryBackend()
        msg = Message(role="user", content="Hello")
        await backend.add_message("t1", msg)

        messages = await backend.get_messages("t1")
        assert len(messages) == 1
        assert messages[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_get_empty_thread(self):
        backend = MemoryBackend()
        messages = await backend.get_messages("nonexistent")
        assert messages == []

    @pytest.mark.asyncio
    async def test_multiple_messages_ordered(self):
        backend = MemoryBackend()
        await backend.add_message("t1", Message(role="user", content="First"))
        await backend.add_message("t1", Message(role="assistant", content="Second"))
        await backend.add_message("t1", Message(role="user", content="Third"))

        messages = await backend.get_messages("t1")
        assert len(messages) == 3
        assert messages[0].content == "First"
        assert messages[2].content == "Third"

    @pytest.mark.asyncio
    async def test_thread_isolation(self):
        backend = MemoryBackend()
        await backend.add_message("t1", Message(role="user", content="Thread 1"))
        await backend.add_message("t2", Message(role="user", content="Thread 2"))

        t1 = await backend.get_messages("t1")
        t2 = await backend.get_messages("t2")
        assert len(t1) == 1
        assert len(t2) == 1
        assert t1[0].content == "Thread 1"
        assert t2[0].content == "Thread 2"

    @pytest.mark.asyncio
    async def test_clear_thread(self):
        backend = MemoryBackend()
        await backend.add_message("t1", Message(role="user", content="Hello"))
        await backend.clear_thread("t1")

        messages = await backend.get_messages("t1")
        assert messages == []

    @pytest.mark.asyncio
    async def test_clear_nonexistent_thread(self):
        backend = MemoryBackend()
        # Should not raise
        await backend.clear_thread("nonexistent")

    @pytest.mark.asyncio
    async def test_list_threads(self):
        backend = MemoryBackend()
        await backend.add_message("t1", Message(role="user", content="A"))
        await backend.add_message("t2", Message(role="user", content="B"))

        threads = await backend.list_threads(100)
        assert len(threads) == 2
        thread_ids = {t["thread_id"] for t in threads}
        assert "t1" in thread_ids
        assert "t2" in thread_ids

    @pytest.mark.asyncio
    async def test_list_threads_empty(self):
        backend = MemoryBackend()
        threads = await backend.list_threads(100)
        assert threads == []

    @pytest.mark.asyncio
    async def test_list_threads_includes_count(self):
        backend = MemoryBackend()
        await backend.add_message("t1", Message(role="user", content="A"))
        await backend.add_message("t1", Message(role="assistant", content="B"))

        threads = await backend.list_threads(100)
        assert threads[0]["message_count"] == 2

    @pytest.mark.asyncio
    async def test_cleanup_old_threads(self):
        backend = MemoryBackend()

        # Add a message with old timestamp
        old_msg = Message(
            role="user",
            content="Old",
            timestamp=datetime.now(timezone.utc) - timedelta(days=60),
        )
        await backend.add_message("old_thread", old_msg)

        # Add a recent message
        await backend.add_message("new_thread", Message(role="user", content="New"))

        # Cleanup threads older than 30 days
        deleted = await backend.cleanup_old_threads(30)
        assert deleted == 1

        # Old thread should be gone
        assert await backend.get_messages("old_thread") == []
        # New thread should remain
        assert len(await backend.get_messages("new_thread")) == 1

    @pytest.mark.asyncio
    async def test_get_messages_returns_copy(self):
        """Modifying returned list should not affect backend."""
        backend = MemoryBackend()
        await backend.add_message("t1", Message(role="user", content="Hello"))

        messages = await backend.get_messages("t1")
        messages.clear()  # Modify returned list

        # Backend should still have the message
        assert len(await backend.get_messages("t1")) == 1


class TestConversationMemory:
    """Test ConversationMemory with in-memory backend."""

    @pytest.mark.asyncio
    async def test_add_and_get_history(self):
        mem = ConversationMemory(backend="memory", max_history=10)
        await mem.add_message("t1", "user", "Hello")
        await mem.add_message("t1", "assistant", "Hi!")

        history = await mem.get_history("t1")
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_max_history_window(self):
        mem = ConversationMemory(backend="memory", max_history=3)

        for i in range(10):
            await mem.add_message("t1", "user", f"Message {i}")

        history = await mem.get_history("t1")
        assert len(history) == 3
        assert history[0].content == "Message 7"  # Last 3 of 10
        assert history[2].content == "Message 9"

    @pytest.mark.asyncio
    async def test_custom_limit_overrides_max_history(self):
        mem = ConversationMemory(backend="memory", max_history=10)

        for i in range(5):
            await mem.add_message("t1", "user", f"Message {i}")

        history = await mem.get_history("t1", limit=2)
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_add_message_returns_message(self):
        mem = ConversationMemory(backend="memory")
        msg = await mem.add_message("t1", "user", "Test", metadata={"key": "val"})
        assert isinstance(msg, Message)
        assert msg.content == "Test"
        assert msg.metadata["key"] == "val"

    @pytest.mark.asyncio
    async def test_clear_thread(self):
        mem = ConversationMemory(backend="memory")
        await mem.add_message("t1", "user", "Hello")
        await mem.clear_thread("t1")

        history = await mem.get_history("t1")
        assert history == []

    @pytest.mark.asyncio
    async def test_list_threads(self):
        mem = ConversationMemory(backend="memory")
        await mem.add_message("t1", "user", "A")
        await mem.add_message("t2", "user", "B")

        threads = await mem.list_threads()
        assert len(threads) == 2

    @pytest.mark.asyncio
    async def test_get_thread_stats_empty(self):
        mem = ConversationMemory(backend="memory")
        stats = await mem.get_thread_stats("nonexistent")
        assert stats["message_count"] == 0
        assert stats["first_message"] is None

    @pytest.mark.asyncio
    async def test_get_thread_stats_with_messages(self):
        mem = ConversationMemory(backend="memory")
        await mem.add_message("t1", "user", "A")
        await mem.add_message("t1", "assistant", "B")

        stats = await mem.get_thread_stats("t1")
        assert stats["message_count"] == 2
        assert stats["first_message"] is not None
        assert stats["last_message"] is not None

    @pytest.mark.asyncio
    async def test_cleanup_disabled_when_days_zero(self):
        mem = ConversationMemory(backend="memory", auto_cleanup_days=0)
        count = await mem.cleanup_old_threads()
        assert count == 0
