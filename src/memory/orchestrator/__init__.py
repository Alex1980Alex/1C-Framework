"""
Memory Orchestrator — Unified Memory System.

Provides UnifiedID namespace, Link Registry, MemoryCube abstraction,
Auto-classify middleware, and Federated Search with Hybrid RRF fusion
across all memory subsystems (AI Memory, Vector Memory, Skill Learning).

Phase 49: Unified Memory System migration from 1C-Enterprise_Framework.
P0 completion: MemCube, Auto-classify, Hybrid RRF.
"""

from .link_registry import (
    EntityLink,
    LinkRegistry,
    LinkType,
    RelatedEntity,
    get_link_registry,
    set_link_registry,
)
from .memcube import (
    ContentType,
    MemoryCube,
)
from .memory_orchestrator import (
    EntityNotFoundError,
    InvalidLinkError,
    MemoryOrchestrator,
    OrchestratorConfig,
    OrchestratorError,
    SubsystemUnavailableError,
)
from .memory_router import (
    CONTENT_TYPE_TARGETS,
    ClassificationResult,
    ContentClassifier,
    MemoryRouter,
    RouterConfig,
    RoutingDecision,
    RoutingStats,
    route_memory,
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
    RRFMerger,
    ScoreNormalizer,
    SearchOptions,
    SearchResultItem,
    SourceError,
    UnifiedSearchEngine,
    UnifiedSearchResult,
    federated_search,
)

__version__ = "1.2.0"

__all__ = [
    # MemoryCube
    "ContentType",
    "MemoryCube",
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
    # MemoryRouter + Auto-classify
    "MemoryRouter",
    "RouterConfig",
    "RoutingDecision",
    "RoutingStats",
    "ClassificationResult",
    "ContentClassifier",
    "CONTENT_TYPE_TARGETS",
    "route_memory",
    # MemoryOrchestrator
    "MemoryOrchestrator",
    "OrchestratorConfig",
    "OrchestratorError",
    "EntityNotFoundError",
    "InvalidLinkError",
    "SubsystemUnavailableError",
    # UnifiedSearch + RRF
    "SearchOptions",
    "SearchResultItem",
    "LinkedEntity",
    "SourceError",
    "UnifiedSearchResult",
    "BaseSearchAdapter",
    "ScoreNormalizer",
    "RRFMerger",
    "Deduplicator",
    "Reranker",
    "LinkEnricher",
    "UnifiedSearchEngine",
    "federated_search",
]
