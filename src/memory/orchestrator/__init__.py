"""
Memory Orchestrator — Unified Memory System.

Provides UnifiedID namespace, Link Registry, and Federated Search
across all memory subsystems (AI Memory, Vector Memory, Skill Learning).

Phase 49: Unified Memory System migration from 1C-Enterprise_Framework.
"""

from .link_registry import (
    EntityLink,
    LinkRegistry,
    LinkType,
    RelatedEntity,
    get_link_registry,
    set_link_registry,
)
from .unified_id import (
    IDRegistry,
    MemoryType,
    SourceServer,
    UnifiedID,
    create_doc_id,
    create_episodic_id,
    create_semantic_id,
    get_registry,
    set_registry,
)
from .unified_search import (
    BaseSearchAdapter,
    Deduplicator,
    LinkedEntity,
    LinkEnricher,
    Reranker,
    ScoreNormalizer,
    SearchOptions,
    SearchResultItem,
    SourceError,
    UnifiedSearchEngine,
    UnifiedSearchResult,
    federated_search,
)

__version__ = "1.0.0"

__all__ = [
    # UnifiedID
    "MemoryType",
    "SourceServer",
    "UnifiedID",
    "IDRegistry",
    "create_episodic_id",
    "create_semantic_id",
    "create_doc_id",
    "get_registry",
    "set_registry",
    # LinkRegistry
    "LinkType",
    "EntityLink",
    "RelatedEntity",
    "LinkRegistry",
    "get_link_registry",
    "set_link_registry",
    # UnifiedSearch
    "SearchOptions",
    "SearchResultItem",
    "LinkedEntity",
    "SourceError",
    "UnifiedSearchResult",
    "BaseSearchAdapter",
    "ScoreNormalizer",
    "Deduplicator",
    "Reranker",
    "LinkEnricher",
    "UnifiedSearchEngine",
    "federated_search",
]
