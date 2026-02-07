"""Abstract base class for graph store implementations.

All graph store providers (Neo4j, NetworkX) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.pdf_framework.schemas.entities import Entity, Relation, SubGraph


class BaseGraphStore(ABC):
    """Abstract interface for graph store operations."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the graph store connection."""

    @abstractmethod
    async def add_entity(self, entity: Entity) -> str:
        """Add an entity node. Returns entity ID."""

    @abstractmethod
    async def add_relation(self, relation: Relation) -> str:
        """Add a relation edge. Returns relation ID."""

    @abstractmethod
    async def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID."""

    @abstractmethod
    async def find_entities(
        self,
        name: str | None = None,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> list[Entity]:
        """Search for entities by name or type."""

    @abstractmethod
    async def get_neighbors(
        self,
        entity_id: str,
        relation_type: str | None = None,
        depth: int = 1,
    ) -> SubGraph:
        """Get neighboring entities up to a given depth."""

    @abstractmethod
    async def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> SubGraph:
        """Find shortest path between two entities."""

    @abstractmethod
    async def query(
        self,
        query_str: str,
        params: dict[str, Any] | None = None,
    ) -> SubGraph:
        """Execute a native query (Cypher for Neo4j, custom for NetworkX)."""

    @abstractmethod
    async def get_statistics(self) -> dict[str, Any]:
        """Return graph statistics: node count, edge count, etc."""

    @abstractmethod
    async def delete_entity(self, entity_id: str) -> None:
        """Delete entity and all its relations."""

    @abstractmethod
    async def clear(self) -> None:
        """Remove all entities and relations."""
