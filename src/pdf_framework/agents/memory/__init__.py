"""Conversation memory for multi-turn dialog support (Phase 9).

Provides:
- Message model for storing conversation turns
- MemoryBackend: in-memory storage for dev/testing
- SQLiteBackend: persistent storage for production
- ConversationMemory: unified API for history management
"""

# Import conversation first (it has no dependency on backends at module level)
from src.pdf_framework.agents.memory.conversation import ConversationMemory, Message

# Then import backends (which depend on Message from conversation)
from src.pdf_framework.agents.memory.backends import MemoryBackend, SQLiteBackend

__all__ = [
    "Message",
    "ConversationMemory",
    "MemoryBackend",
    "SQLiteBackend",
]
