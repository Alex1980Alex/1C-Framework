"""Graph store providers and community detection.

Phase 6 (v0.7.0) - GraphRAG:
- Community Detection via Leiden algorithm
- Community Summaries via LLM
- Local Search (graph-enhanced vector search)
- Global Search (map-reduce over communities)

Phase 61 - Incremental Graph Update:
- Change detection for chunks
- Partial re-extraction of entities
- Incremental entity embedding updates
"""

from src.pdf_framework.config import GraphStoreSettings
from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.graph_store.change_detector import (
    ChangeSet,
    GraphChangeDetector,
    get_change_detector,
)
from src.pdf_framework.graph_store.incremental import (
    IncrementalGraphUpdater,
    get_incremental_updater,
)


def get_graph_store(settings: GraphStoreSettings | None = None) -> BaseGraphStore:
    """Factory: return a graph store based on settings."""
    settings = settings or GraphStoreSettings()
    if settings.provider == "networkx":
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        return NetworkXGraphStore(settings)
    if settings.provider == "neo4j":
        from src.pdf_framework.graph_store.providers.neo4j_store import Neo4jGraphStore

        return Neo4jGraphStore(settings)
    raise ValueError(f"Unsupported graph store provider: {settings.provider}")


__all__ = [
    "BaseGraphStore",
    "GraphStoreSettings",
    "get_graph_store",
    # Phase 61: Incremental Update
    "ChangeSet",
    "GraphChangeDetector",
    "get_change_detector",
    "IncrementalGraphUpdater",
    "get_incremental_updater",
]
