"""Tenant-isolated graph store (Phase 12.2).

Filters graph queries by tenant_id for data isolation.

Author: Claude Code
Version: 1.3.0 - Phase 12.2: Tenant Graph Isolation
"""

import logging
import re
from pathlib import Path
from typing import Any

from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.schemas.entities import Entity, Relation, SubGraph

logger = logging.getLogger(__name__)


class TenantGraphStore(BaseGraphStore):
    """
    Tenant-scoped graph store wrapper.

    Wraps a base graph store and automatically filters all queries by tenant_id.
    Each tenant has a separate JSON file for persistence.
    """

    def __init__(
        self,
        tenant_id: str,
        base_store_class: type[BaseGraphStore],
        graph_dir: str | Path = "data/graph_db",
    ):
        """
        Initialize tenant-scoped graph store.

        Args:
            tenant_id: Tenant identifier
            base_store_class: Base graph store class to wrap
            graph_dir: Directory for tenant graph files
        """
        self._tenant_id = tenant_id
        self._graph_dir = Path(graph_dir)
        self._graph_dir.mkdir(parents=True, exist_ok=True)

        # Tenant-specific graph file
        sanitized = _sanitize_tenant_id(tenant_id)
        self._graph_path = self._graph_dir / f"tenant_{sanitized}.json"

        # Create base store with tenant-specific path
        self._base_store = base_store_class()
        if hasattr(self._base_store, "_persist_path"):
            self._base_store._persist_path = self._graph_path

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the tenant graph store."""
        if self._initialized:
            return

        await self._base_store.initialize()
        self._initialized = True

        # Add tenant_id to existing nodes without it
        await self._ensure_tenant_attributes()

    async def _ensure_tenant_attributes(self) -> None:
        """Ensure all nodes and edges have tenant_id in properties."""
        try:
            graph = self._base_store._graph
            for node in graph.nodes():
                node_data = graph.nodes[node]
                props = node_data.get("properties", {})
                if "tenant_id" not in props:
                    props["tenant_id"] = self._tenant_id
                    node_data["properties"] = props

            for u, v in graph.edges():
                edge_data = graph.edges[u, v]
                props = edge_data.get("properties", {})
                if "tenant_id" not in props:
                    props["tenant_id"] = self._tenant_id
                    edge_data["properties"] = props

            # Save if modified
            if hasattr(self._base_store, "_save_to_file"):
                self._base_store._save_to_file()

        except Exception as e:
            logger.warning(f"[TENANT_GRAPH] Could not ensure tenant attributes: {e}")

    async def add_entity(self, entity: Entity) -> str:
        """Add entity with tenant_id."""
        entity.properties["tenant_id"] = self._tenant_id
        return await self._base_store.add_entity(entity)

    async def add_relation(self, relation: Relation) -> str:
        """Add relation with tenant_id."""
        relation.properties["tenant_id"] = self._tenant_id
        return await self._base_store.add_relation(relation)

    async def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity (tenant-scoped)."""
        entity = await self._base_store.get_entity(entity_id)
        if entity and entity.properties.get("tenant_id") == self._tenant_id:
            return entity
        return None

    async def find_entities(
        self,
        name: str | None = None,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> list[Entity]:
        """Find entities (filtered by tenant_id)."""
        # Over-fetch and filter by tenant
        results = await self._base_store.find_entities(
            name=name,
            entity_type=entity_type,
            limit=limit * 3,
        )
        return [
            e for e in results
            if e.properties.get("tenant_id") == self._tenant_id
        ][:limit]

    async def get_neighbors(
        self,
        entity_id: str,
        relation_type: str | None = None,
        depth: int = 1,
    ) -> SubGraph:
        """Get neighbors (tenant-scoped)."""
        # Verify entity belongs to tenant
        entity = await self.get_entity(entity_id)
        if not entity:
            return SubGraph()

        subgraph = await self._base_store.get_neighbors(
            entity_id, relation_type, depth
        )

        # Filter by tenant_id
        subgraph.entities = [
            e for e in subgraph.entities
            if e.properties.get("tenant_id") == self._tenant_id
        ]
        subgraph.relations = [
            r for r in subgraph.relations
            if r.properties.get("tenant_id") == self._tenant_id
        ]
        return subgraph

    async def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> SubGraph:
        """Find path (tenant-scoped)."""
        # Verify both entities belong to tenant
        from_entity = await self.get_entity(source_id)
        to_entity = await self.get_entity(target_id)

        if not from_entity or not to_entity:
            return SubGraph()

        return await self._base_store.find_path(source_id, target_id, max_depth)

    async def query(
        self,
        query_str: str,
        params: dict[str, Any] | None = None,
    ) -> SubGraph:
        """Execute query (filtered by tenant_id)."""
        result = await self._base_store.query(query_str, params)

        # Filter results by tenant_id
        result.entities = [
            e for e in result.entities
            if e.properties.get("tenant_id") == self._tenant_id
        ]
        result.relations = [
            r for r in result.relations
            if r.properties.get("tenant_id") == self._tenant_id
        ]
        return result

    async def get_statistics(self) -> dict[str, Any]:
        """Get statistics (tenant-scoped)."""
        stats = await self._base_store.get_statistics()

        # Recalculate to only count tenant's data
        try:
            graph = self._base_store._graph
            tenant_nodes = [
                n for n, attrs in graph.nodes(data=True)
                if attrs.get("properties", {}).get("tenant_id") == self._tenant_id
            ]
            tenant_edges = [
                (u, v) for u, v, attrs in graph.edges(data=True)
                if attrs.get("properties", {}).get("tenant_id") == self._tenant_id
            ]

            stats["entity_count"] = len(tenant_nodes)
            stats["relation_count"] = len(tenant_edges)

        except Exception:
            pass

        return stats

    async def delete_entity(self, entity_id: str) -> None:
        """Delete entity (tenant-scoped)."""
        entity = await self.get_entity(entity_id)
        if entity:
            await self._base_store.delete_entity(entity_id)

    async def clear(self) -> None:
        """Clear all tenant data."""
        await self._base_store.clear()

    async def delete_tenant_data(self) -> None:
        """Delete all data for this tenant (GDPR)."""
        await self.clear()

        # Delete graph file
        if self._graph_path.exists():
            self._graph_path.unlink()

        logger.info(f"[TENANT_GRAPH] Deleted all data for tenant '{self._tenant_id}'")


def _sanitize_tenant_id(tenant_id: str) -> str:
    """Sanitize tenant ID for file names."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", tenant_id)[:63]


class TenantGraphManager:
    """
    Manages tenant-isolated graph stores.

    Similar to TenantVectorStoreManager but for graph data.
    """

    def __init__(
        self,
        base_store_class: type[BaseGraphStore] | None = None,
        graph_dir: str | Path = "data/graph_db",
    ):
        """
        Initialize tenant graph manager.

        Args:
            base_store_class: Base graph store class
            graph_dir: Directory for tenant graph files
        """
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        self._base_store_class = base_store_class or NetworkXGraphStore
        self._graph_dir = Path(graph_dir)
        self._graph_dir.mkdir(parents=True, exist_ok=True)

        # Cache of active stores
        self._store_cache: dict[str, TenantGraphStore] = {}

    async def get_store(self, tenant_id: str) -> TenantGraphStore:
        """Get or create graph store for tenant."""
        if tenant_id not in self._store_cache:
            store = TenantGraphStore(
                tenant_id=tenant_id,
                base_store_class=self._base_store_class,
                graph_dir=self._graph_dir,
            )
            await store.initialize()
            self._store_cache[tenant_id] = store

        return self._store_cache[tenant_id]

    async def delete_tenant(self, tenant_id: str) -> None:
        """Delete tenant graph data."""
        if tenant_id in self._store_cache:
            await self._store_cache[tenant_id].delete_tenant_data()
            del self._store_cache[tenant_id]

        # Also delete graph file if exists
        sanitized = _sanitize_tenant_id(tenant_id)
        graph_path = self._graph_dir / f"tenant_{sanitized}.json"
        if graph_path.exists():
            graph_path.unlink()

    async def list_tenants(self) -> list[str]:
        """List tenants with graph data."""
        tenants = []
        for graph_file in self._graph_dir.glob("tenant_*.json"):
            # Extract tenant_id from filename
            tenant_id = graph_file.stem.replace("tenant_", "")
            tenants.append(tenant_id)
        return sorted(tenants)


# Global tenant graph manager instance
_tenant_graph_manager: TenantGraphManager | None = None


def get_tenant_graph_manager(**kwargs) -> TenantGraphManager:
    """Get or create global tenant graph manager instance."""
    global _tenant_graph_manager
    if _tenant_graph_manager is None:
        _tenant_graph_manager = TenantGraphManager(**kwargs)
    return _tenant_graph_manager
