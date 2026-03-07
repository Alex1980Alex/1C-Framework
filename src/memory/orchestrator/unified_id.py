"""
Unified ID System for Memory Subsystems.

Provides a unified ID namespace for cross-referencing entities across
different memory servers:
- memory-ai (EPISODIC)
- vector-memory (SEMANTIC)
- skill-learning (LEARNING)
- pdf-docs (DOCUMENTATION)

Format: {memory_type}:{source}:{identifier}
Example: episodic:memory-ai:550e8400-e29b-41d4-a716-446655440000

Migrated from D:\\1C-Enterprise_Framework\\memory-orchestrator\\src\\unified_id.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import hashlib
import re
import uuid


class MemoryType(Enum):
    """Types of memory in the unified namespace."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    LEARNING = "learning"
    DOCUMENTATION = "docs"

    @classmethod
    def from_string(cls, value: str) -> "MemoryType":
        value = value.lower()
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Unknown memory type: {value}")


class SourceServer(Enum):
    """Source MCP servers for memory operations."""

    MEMORY_AI = "memory-ai"
    VECTOR_MEMORY = "vector-memory"
    SKILL_LEARNING = "skill-learning"
    PDF_DOCS = "pdf-docs"
    ORCHESTRATOR = "orchestrator"

    @classmethod
    def from_string(cls, value: str) -> "SourceServer":
        value = value.lower()
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Unknown source server: {value}")

    @property
    def memory_type(self) -> MemoryType:
        mapping = {
            SourceServer.MEMORY_AI: MemoryType.EPISODIC,
            SourceServer.VECTOR_MEMORY: MemoryType.SEMANTIC,
            SourceServer.SKILL_LEARNING: MemoryType.LEARNING,
            SourceServer.PDF_DOCS: MemoryType.DOCUMENTATION,
            SourceServer.ORCHESTRATOR: MemoryType.EPISODIC,
        }
        return mapping[self]


@dataclass
class UnifiedID:
    """
    Unified identifier for cross-server memory references.

    Format: {memory_type}:{source}:{identifier}
    """

    memory_type: MemoryType
    source: SourceServer
    identifier: str
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    _IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_:\-]+$")

    def __post_init__(self):
        if not self._IDENTIFIER_PATTERN.match(self.identifier):
            raise ValueError(
                f"Invalid identifier format: {self.identifier}. "
                "Must contain only alphanumeric, underscore, colon, or hyphen."
            )

    @property
    def unified(self) -> str:
        return f"{self.memory_type.value}:{self.source.value}:{self.identifier}"

    @property
    def short_id(self) -> str:
        return self.identifier[-8:] if len(self.identifier) > 8 else self.identifier

    def __str__(self) -> str:
        return self.unified

    def __hash__(self) -> int:
        return hash(self.unified)

    def __eq__(self, other) -> bool:
        if isinstance(other, UnifiedID):
            return self.unified == other.unified
        if isinstance(other, str):
            return self.unified == other
        return False

    @classmethod
    def parse(cls, unified_id: str) -> "UnifiedID":
        parts = unified_id.split(":", 2)
        if len(parts) != 3:
            raise ValueError(
                f"Invalid unified ID format: {unified_id}. "
                "Expected format: type:source:identifier"
            )
        return cls(
            memory_type=MemoryType.from_string(parts[0]),
            source=SourceServer.from_string(parts[1]),
            identifier=parts[2],
        )

    @classmethod
    def from_original(
        cls,
        source: SourceServer,
        original_id: str,
        memory_type: Optional[MemoryType] = None,
    ) -> "UnifiedID":
        return cls(
            memory_type=memory_type or source.memory_type,
            source=source,
            identifier=original_id,
        )

    @classmethod
    def generate(
        cls,
        source: SourceServer,
        memory_type: Optional[MemoryType] = None,
    ) -> "UnifiedID":
        return cls(
            memory_type=memory_type or source.memory_type,
            source=source,
            identifier=str(uuid.uuid4()),
        )

    @classmethod
    def from_path(
        cls,
        source: SourceServer,
        path: str,
        project_id: Optional[str] = None,
    ) -> "UnifiedID":
        input_str = f"{project_id}:{path}" if project_id else path
        hash_id = hashlib.sha256(input_str.encode()).hexdigest()[:16]
        return cls(
            memory_type=MemoryType.DOCUMENTATION,
            source=source,
            identifier=hash_id,
        )

    def to_original(self) -> str:
        return self.identifier

    def with_metadata(self, **kwargs) -> "UnifiedID":
        return UnifiedID(
            memory_type=self.memory_type,
            source=self.source,
            identifier=self.identifier,
            created_at=self.created_at,
            metadata={**self.metadata, **kwargs},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unified_id": self.unified,
            "memory_type": self.memory_type.value,
            "source": self.source.value,
            "identifier": self.identifier,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedID":
        return cls(
            memory_type=MemoryType.from_string(data["memory_type"]),
            source=SourceServer.from_string(data["source"]),
            identifier=data["identifier"],
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
        )


class IDRegistry:
    """
    Registry for tracking and resolving unified IDs.

    Provides bi-directional mapping (unified <-> original),
    batch operations, and export/import for persistence.
    """

    def __init__(self):
        self._unified_to_original: Dict[str, str] = {}
        self._original_to_unified: Dict[str, str] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def register(self, unified_id: UnifiedID, original_id: Optional[str] = None) -> str:
        uid_str = unified_id.unified
        orig_id = original_id or unified_id.identifier

        if uid_str in self._unified_to_original:
            existing = self._unified_to_original[uid_str]
            if existing != orig_id:
                raise ValueError(
                    f"Unified ID {uid_str} already mapped to {existing}, "
                    f"cannot remap to {orig_id}"
                )

        self._unified_to_original[uid_str] = orig_id
        source_key = f"{unified_id.source.value}:{orig_id}"
        self._original_to_unified[source_key] = uid_str
        self._metadata[uid_str] = unified_id.to_dict()
        return uid_str

    def resolve(self, unified_id: str) -> Optional[str]:
        return self._unified_to_original.get(unified_id)

    def lookup(self, source: SourceServer, original_id: str) -> Optional[str]:
        source_key = f"{source.value}:{original_id}"
        return self._original_to_unified.get(source_key)

    def get_or_create(
        self,
        source: SourceServer,
        original_id: str,
        memory_type: Optional[MemoryType] = None,
    ) -> UnifiedID:
        existing = self.lookup(source, original_id)
        if existing:
            return UnifiedID.parse(existing)
        unified_id = UnifiedID.from_original(source, original_id, memory_type)
        self.register(unified_id, original_id)
        return unified_id

    def batch_register(
        self, items: List[tuple]
    ) -> List[UnifiedID]:
        results = []
        for source, original_id, memory_type in items:
            unified_id = self.get_or_create(source, original_id, memory_type)
            results.append(unified_id)
        return results

    def export(self) -> Dict[str, Any]:
        return {
            "unified_to_original": self._unified_to_original,
            "original_to_unified": self._original_to_unified,
            "metadata": self._metadata,
        }

    def import_state(self, state: Dict[str, Any]):
        self._unified_to_original = state.get("unified_to_original", {})
        self._original_to_unified = state.get("original_to_unified", {})
        self._metadata = state.get("metadata", {})

    def stats(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        by_source: Dict[str, int] = {}

        for uid_str in self._unified_to_original:
            try:
                uid = UnifiedID.parse(uid_str)
                by_type[uid.memory_type.value] = by_type.get(uid.memory_type.value, 0) + 1
                by_source[uid.source.value] = by_source.get(uid.source.value, 0) + 1
            except ValueError:
                pass

        return {
            "total_ids": len(self._unified_to_original),
            "by_memory_type": by_type,
            "by_source": by_source,
        }


# Convenience functions

def create_episodic_id(source: SourceServer) -> UnifiedID:
    if source.memory_type != MemoryType.EPISODIC:
        raise ValueError(f"Server {source.value} is not an episodic memory source")
    return UnifiedID.generate(source, MemoryType.EPISODIC)


def create_semantic_id() -> UnifiedID:
    return UnifiedID.generate(SourceServer.VECTOR_MEMORY, MemoryType.SEMANTIC)


def create_doc_id(path: str, project_id: Optional[str] = None) -> UnifiedID:
    return UnifiedID.from_path(SourceServer.PDF_DOCS, path, project_id)


# Global registry instance
_global_registry = IDRegistry()


def get_registry() -> IDRegistry:
    return _global_registry


def set_registry(registry: IDRegistry):
    global _global_registry
    _global_registry = registry
