"""Conversation memory for multi-turn dialog support (Phase 9).

Provides:
- Message model for storing conversation turns
- MemoryBackend: in-memory storage for dev/testing
- SQLiteBackend: persistent storage for production
- ConversationMemory: unified API for history management
"""

from src.pdf_framework.agents.memory.backends import MemoryBackend, SQLiteBackend
from src.pdf_framework.agents.memory.conversation import ConversationMemory, Message

__all__ = [
    "Message",
    "ConversationMemory",
    "MemoryBackend",
    "SQLiteBackend",
]
