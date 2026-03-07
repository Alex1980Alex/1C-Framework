"""
Unified Search Engine — Federated Search Across Memory Subsystems.

Architecture: Dispatcher -> Parallel searches -> Normalize -> Deduplicate -> Rerank -> Enrich

Migrated from D:\\1C-Enterprise_Framework\\memory-orchestrator\\src\\unified_search.py
"""

import asyncio
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .link_registry import LinkRegistry, get_link_registry
from .unified_id import MemoryType, SourceServer

logger = logging.getLogger(__name__)


@dataclass
class SearchOptions:
    """Configuration for federated search."""

    search_type: str = "hybrid"
    timeout_ms: int = 5000
    dedup_enabled: bool = True
    boost_recent: bool = True
    boost_high_confidence: bool = True
    diversity_enabled: bool = True
    max_link_depth: int = 1
    min_link_strength: float = 0.5


@dataclass
class LinkedEntity:
    """Cross-reference from Link Registry."""

    target_id: str
    link_type: str
    strength: float
    direction: str = "outgoing"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "link_type": self.link_type,
            "strength": self.strength,
            "direction": self.direction,
        }


@dataclass
class SourceError:
    """Tracking search failure for a source."""

    source: str
    error: str
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {"source": self.source, "error": self.error, "duration_ms": self.duration_ms}


@dataclass
class SearchResultItem:
    """Individual result from federated search."""

    unified_id: str
    source: SourceServer
    memory_type: MemoryType
    content: str
    title: Optional[str] = None
    snippet: Optional[str] = None
    raw_score: float = 0.5
    normalized_score: float = 0.5
    final_score: float = 0.5
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    linked_entities: List[LinkedEntity] = field(default_factory=list)
    duplicate_sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unified_id": self.unified_id,
            "source": self.source.value,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "title": self.title,
            "snippet": self.snippet or self.content[:200],
            "raw_score": self.raw_score,
            "normalized_score": self.normalized_score,
            "final_score": self.final_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "tags": self.tags,
            "metadata": self.metadata,
            "linked_entities": [le.to_dict() for le in self.linked_entities],
            "duplicate_sources": self.duplicate_sources,
        }


@dataclass
class UnifiedSearchResult:
    """Container for federated search results."""

    query: str
    total_results: int
    results: List[SearchResultItem]
    search_time_ms: float
    sources_searched: List[str]
    sources_failed: List[SourceError] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "total_results": self.total_results,
            "results": [r.to_dict() for r in self.results],
            "search_time_ms": self.search_time_ms,
            "sources_searched": self.sources_searched,
            "sources_failed": [e.to_dict() for e in self.sources_failed],
            "metadata": self.metadata,
        }


class BaseSearchAdapter(ABC):
    """Protocol for pluggable search sources."""

    @abstractmethod
    async def search(
        self, query: str, limit: int = 10, **kwargs
    ) -> List[SearchResultItem]:
        ...

    @abstractmethod
    def source_name(self) -> str:
        ...


class ScoreNormalizer:
    """Normalize raw scores from different sources to 0-1 scale."""

    BOOST_RECENT_24H = 1.2
    BOOST_RECENT_WEEK = 1.1
    BOOST_HIGH_CONFIDENCE = 1.15
    BOOST_HAS_LINKS = 1.1

    def normalize(self, item: SearchResultItem, options: SearchOptions) -> float:
        score = min(max(item.raw_score, 0.0), 1.0)

        if options.boost_recent and item.created_at:
            age = datetime.now() - item.created_at
            if age < timedelta(hours=24):
                score *= self.BOOST_RECENT_24H
            elif age < timedelta(days=7):
                score *= self.BOOST_RECENT_WEEK

        if options.boost_high_confidence and item.raw_score > 0.8:
            score *= self.BOOST_HIGH_CONFIDENCE

        return min(score, 1.0)


class Deduplicator:
    """Deduplicate results using content hashing."""

    def deduplicate(
        self, items: List[SearchResultItem],
    ) -> List[SearchResultItem]:
        seen_hashes: Dict[str, SearchResultItem] = {}
        result = []

        for item in items:
            content_hash = hashlib.md5(item.content.strip().lower().encode()).hexdigest()
            if content_hash in seen_hashes:
                seen_hashes[content_hash].duplicate_sources.append(item.source.value)
            else:
                seen_hashes[content_hash] = item
                result.append(item)

        return result


class Reranker:
    """Rerank results with diversity enforcement."""

    def rerank(
        self, items: List[SearchResultItem], options: SearchOptions,
    ) -> List[SearchResultItem]:
        sorted_items = sorted(items, key=lambda x: x.final_score, reverse=True)

        if not options.diversity_enabled:
            return sorted_items

        # Ensure source diversity: don't let one source dominate top results
        reranked = []
        source_counts: Dict[str, int] = {}
        remaining = list(sorted_items)

        while remaining:
            for i, item in enumerate(remaining):
                source_key = item.source.value
                count = source_counts.get(source_key, 0)
                # Allow max 3 from same source in top positions
                if count < 3 or len(reranked) >= 10:
                    reranked.append(item)
                    source_counts[source_key] = count + 1
                    remaining.pop(i)
                    break
            else:
                reranked.extend(remaining)
                break

        return reranked


class LinkEnricher:
    """Enrich results with cross-references from Link Registry."""

    def __init__(self, link_registry: Optional[LinkRegistry] = None):
        self._registry = link_registry

    def enrich(
        self, items: List[SearchResultItem], max_depth: int = 1, min_strength: float = 0.5,
    ) -> List[SearchResultItem]:
        if not self._registry:
            return items

        for item in items:
            try:
                all_links = self._registry.get_all_links(item.unified_id, min_strength=min_strength)
                for link in all_links.get("outgoing", []):
                    item.linked_entities.append(LinkedEntity(
                        target_id=link.target_id,
                        link_type=link.link_type.value,
                        strength=link.strength,
                        direction="outgoing",
                    ))
                for link in all_links.get("incoming", []):
                    item.linked_entities.append(LinkedEntity(
                        target_id=link.source_id,
                        link_type=link.link_type.value,
                        strength=link.strength,
                        direction="incoming",
                    ))
            except Exception as e:
                logger.warning(f"Failed to enrich {item.unified_id}: {e}")

        return items


class UnifiedSearchEngine:
    """Orchestrates federated search across all memory subsystems."""

    def __init__(self, link_registry: Optional[LinkRegistry] = None):
        self._adapters: Dict[str, BaseSearchAdapter] = {}
        self._normalizer = ScoreNormalizer()
        self._deduplicator = Deduplicator()
        self._reranker = Reranker()
        self._enricher = LinkEnricher(link_registry)

    def register_adapter(self, adapter: BaseSearchAdapter):
        self._adapters[adapter.source_name()] = adapter

    def unregister_adapter(self, name: str):
        self._adapters.pop(name, None)

    async def search(
        self,
        query: str,
        sources: Optional[List[SourceServer]] = None,
        memory_types: Optional[List[MemoryType]] = None,
        min_score: float = 0.3,
        limit: int = 20,
        include_links: bool = True,
        options: Optional[SearchOptions] = None,
    ) -> UnifiedSearchResult:
        options = options or SearchOptions()
        start = time.time()

        # Filter adapters by requested sources
        adapters = self._adapters
        if sources:
            source_names = {s.value for s in sources}
            adapters = {k: v for k, v in adapters.items() if k in source_names}

        # Run searches in parallel with timeout
        tasks = {}
        for name, adapter in adapters.items():
            tasks[name] = asyncio.create_task(
                asyncio.wait_for(
                    adapter.search(query, limit=limit),
                    timeout=options.timeout_ms / 1000,
                )
            )

        all_results: List[SearchResultItem] = []
        sources_searched = []
        sources_failed = []

        for name, task in tasks.items():
            task_start = time.time()
            try:
                results = await task
                all_results.extend(results)
                sources_searched.append(name)
            except asyncio.TimeoutError:
                duration_ms = (time.time() - task_start) * 1000
                sources_failed.append(SourceError(source=name, error="timeout", duration_ms=duration_ms))
                logger.warning(f"Search timeout for {name} ({duration_ms:.0f}ms)")
            except Exception as e:
                duration_ms = (time.time() - task_start) * 1000
                sources_failed.append(SourceError(source=name, error=str(e), duration_ms=duration_ms))
                logger.error(f"Search error for {name}: {e}")

        # Filter by memory type
        if memory_types:
            type_values = {mt.value for mt in memory_types}
            all_results = [r for r in all_results if r.memory_type.value in type_values]

        # Normalize scores
        for item in all_results:
            item.normalized_score = self._normalizer.normalize(item, options)
            item.final_score = item.normalized_score

        # Filter by min score
        all_results = [r for r in all_results if r.final_score >= min_score]

        # Deduplicate
        if options.dedup_enabled:
            all_results = self._deduplicator.deduplicate(all_results, options.dedup_threshold)

        # Rerank
        all_results = self._reranker.rerank(all_results, options)

        # Enrich with links
        if include_links:
            all_results = self._enricher.enrich(
                all_results, options.max_link_depth, options.min_link_strength,
            )

        # Limit results
        all_results = all_results[:limit]

        elapsed_ms = (time.time() - start) * 1000

        return UnifiedSearchResult(
            query=query,
            total_results=len(all_results),
            results=all_results,
            search_time_ms=elapsed_ms,
            sources_searched=sources_searched,
            sources_failed=sources_failed,
            metadata={"options": options.__dict__},
        )


# Global engine instance
_global_engine: Optional[UnifiedSearchEngine] = None


def get_search_engine() -> UnifiedSearchEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = UnifiedSearchEngine()
    return _global_engine


def set_search_engine(engine: UnifiedSearchEngine):
    global _global_engine
    _global_engine = engine


async def federated_search(
    query: str,
    sources: Optional[List[SourceServer]] = None,
    memory_types: Optional[List[MemoryType]] = None,
    min_score: float = 0.3,
    limit: int = 20,
    include_links: bool = True,
    search_options: Optional[SearchOptions] = None,
) -> UnifiedSearchResult:
    """Convenience function for federated search using global engine."""
    engine = get_search_engine()
    return await engine.search(
        query=query,
        sources=sources,
        memory_types=memory_types,
        min_score=min_score,
        limit=limit,
        include_links=include_links,
        options=search_options,
    )
