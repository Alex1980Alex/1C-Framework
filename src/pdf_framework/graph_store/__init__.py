"""Graph store providers and community detection.

Phase 6 (v0.7.0) - GraphRAG:
- Community Detection via Leiden algorithm
- Community Summaries via LLM
- Local Search (graph-enhanced vector search)
- Global Search (map-reduce over communities)
"""

from src.pdf_framework.config import GraphStoreSettings
from src.pdf_framework.graph_store.base import BaseGraphStore


def get_graph_store(settings: GraphStoreSettings | None = None) -> BaseGraphStore:
    """Factory: return a graph store based on settings."""
    settings = settings or GraphStoreSettings()
    if settings.provider == "networkx":
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        return NetworkXGraphStore(settings)
    raise ValueError(f"Unsupported graph store provider: {settings.provider}")


__all__ = [
    "BaseGraphStore",
    "GraphStoreSettings",
    "get_graph_store",
]
