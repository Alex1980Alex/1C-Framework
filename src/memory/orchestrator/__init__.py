"""
Memory Orchestrator — Unified Memory System.

Provides UnifiedID namespace, Link Registry, and Federated Search
across all memory subsystems (AI Memory, Vector Memory, Skill Learning).

Phase 49: Unified Memory System migration from 1C-Enterprise_Framework.
"""

from .unified_id import (
    MemoryType,
    SourceServer,
    UnifiedID,
    IDRegistry,
    create_episodic_id,
    create_semantic_id,
    create_doc_id,
    get_registry,
    set_registry,
)
from .link_registry import (
    LinkType,
    EntityLink,
    RelatedEntity,
    LinkRegistry,
    get_link_registry,
    set_link_registry,
)
from .unified_search import (
    SearchOptions,
    SearchResultItem,
    LinkedEntity,
    SourceError,
    UnifiedSearchResult,
    BaseSearchAdapter,
    ScoreNormalizer,
    Deduplicator,
    Reranker,
    LinkEnricher,
    UnifiedSearchEngine,
    federated_search,
)

__version__ = "1.0.0"

__all__ = [
    # UnifiedID
    "MemoryType", "SourceServer", "UnifiedID", "IDRegistry",
    "create_episodic_id", "create_semantic_id", "create_doc_id",
    "get_registry", "set_registry",
    # LinkRegistry
    "LinkType", "EntityLink", "RelatedEntity", "LinkRegistry",
    "get_link_registry", "set_link_registry",
    # UnifiedSearch
    "SearchOptions", "SearchResultItem", "LinkedEntity", "SourceError",
    "UnifiedSearchResult", "BaseSearchAdapter", "ScoreNormalizer",
    "Deduplicator", "Reranker", "LinkEnricher", "UnifiedSearchEngine",
    "federated_search",
]
