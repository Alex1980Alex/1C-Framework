"""
Base Memory Adapter — Abstract interface for memory backends.

Simplified from unified-memory-mcp/src/adapters/base_adapter.py (255 lines).
Changes:
- Removed UnifiedIDRegistry dependency (use simpler unified_id module)
- Self-contained SearchResult/ContextItem dataclasses
- Focused on 3 backends: ai_memory (SQLite), vector_memory (Qdrant), skill_learning (JSONL)

Version: 2.0 (2026-04-04) — P1 migration
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SaveRequest:
    """Request to save content to a memory backend."""

    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def importance(self) -> float:
        return self.metadata.get("importance", 0.7)

    @property
    def category(self) -> str:
        return self.metadata.get("category", "general")

    @property
    def tags(self) -> List[str]:
        return self.metadata.get("tags", [])


@dataclass
class SearchResult:
    """A single search result from a memory backend."""

    content: str
    score: float  # 0.0-1.0 normalized
    source: str  # backend name
    entity_id: Optional[str] = None
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "score": self.score,
            "source": self.source,
            "entity_id": self.entity_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class BackendStats:
    """Statistics from a memory backend."""

    backend_name: str
    status: str = "healthy"  # healthy, unhealthy, no_data
    total_items: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend_name": self.backend_name,
            "status": self.status,
            "total_items": self.total_items,
            **self.extra,
        }


class BaseMemoryAdapter(ABC):
    """
    Abstract base class for memory backend adapters.

    Each adapter wraps a specific storage backend:
    - AiMemoryAdapter → SQLite (important_messages table)
    - VectorMemoryAdapter → Qdrant (learned_patterns collection)
    - SkillLearningAdapter → JSONL files (patterns.jsonl)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.timeout = config.get("timeout", 5.0)
        self.backend_name = self.__class__.__name__.replace("Adapter", "").lower()

    @abstractmethod
    async def save(self, request: SaveRequest) -> str | None:
        """
        Save content to this backend.

        Returns:
            Entity ID if saved successfully, None on failure.
        """
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        """
        Search this backend.

        Returns:
            List of SearchResult objects, sorted by relevance.
        """
        ...

    @abstractmethod
    async def get(self, entity_id: str) -> Dict[str, Any] | None:
        """
        Get a specific entity by ID.

        Returns:
            Entity data dict, or None if not found.
        """
        ...

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """
        Delete an entity.

        Returns:
            True if deleted, False if not found or unsupported.
        """
        ...

    @abstractmethod
    async def update(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an entity's fields.

        Returns:
            True if updated, False if not found or failed.
        """
        ...

    @abstractmethod
    async def get_stats(self) -> BackendStats:
        """Get backend statistics."""
        ...

    async def health_check(self) -> bool:
        """Check if backend is healthy."""
        try:
            stats = await self.get_stats()
            return stats.status == "healthy"
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} enabled={self.enabled} timeout={self.timeout}>"


__all__ = [
    "BaseMemoryAdapter",
    "BackendStats",
    "SaveRequest",
    "SearchResult",
]
