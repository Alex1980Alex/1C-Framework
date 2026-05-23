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
from typing import Any

from .link_registry import LinkRegistry
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
    # RRF configuration
    rrf_enabled: bool = True
    rrf_k: int = 60
    rrf_source_weights: dict[str, float] | None = None


@dataclass
class LinkedEntity:
    """Cross-reference from Link Registry."""

    target_id: str
    link_type: str
    strength: float
    direction: str = "outgoing"

    def to_dict(self) -> dict[str, Any]:
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

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "error": self.error, "duration_ms": self.duration_ms}


@dataclass
class SearchResultItem:
    """Individual result from federated search."""

    unified_id: str
    source: SourceServer
    memory_type: MemoryType
    content: str
    title: str | None = None
    snippet: str | None = None
    raw_score: float = 0.5
    normalized_score: float = 0.5
    final_score: float = 0.5
    created_at: datetime | None = None
    updated_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    linked_entities: list[LinkedEntity] = field(default_factory=list)
    duplicate_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
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
    results: list[SearchResultItem]
    search_time_ms: float
    sources_searched: list[str]
    sources_failed: list[SourceError] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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
    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResultItem]: ...

    @abstractmethod
    def source_name(self) -> str: ...


class ScoreNormalizer:
    """Normalize raw scores from different sources to 0-1 scale.

    Used as a fallback when RRF fusion is disabled or as pre-processing
    before RRF to ensure raw_score is in [0, 1].
    """

    BOOST_RECENT_24H = 1.2
    BOOST_RECENT_WEEK = 1.1
    BOOST_HIGH_CONFIDENCE = 1.15

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


class RRFMerger:
    """Reciprocal Rank Fusion across multiple source-ranked lists.

    RRF formula: score(d) = SUM over sources S of: weight_S / (k + rank_S(d))

    where k is a smoothing constant (default 60) and rank starts at 1.

    Reference implementations:
    - pdf_framework/search/strategies/hybrid_search.py::_rrf_merge
    - bsl/semantic_search/services/hybrid_search.py::_rrf_fuse
    - bsl/semantic_search/services/dual_vector_search.py::_rrf_fuse_3way
    """

    def __init__(
        self,
        k: int = 60,
        source_weights: dict[str, float] | None = None,
    ):
        self._k = k
        self._source_weights = source_weights or {}

    def fuse(
        self,
        source_results: dict[str, list[SearchResultItem]],
        options: SearchOptions,
    ) -> list[SearchResultItem]:
        """Fuse ranked lists from multiple sources using RRF.

        Args:
            source_results: Mapping of source_name -> ranked result list.
            options: Search options (recency/confidence boosts applied post-RRF).

        Returns:
            Merged list sorted by RRF score (descending), normalized to [0, 1].
        """
        rrf_scores: dict[str, float] = {}
        result_map: dict[str, SearchResultItem] = {}

        normalizer = ScoreNormalizer()

        for source_name, results in source_results.items():
            weight = self._source_weights.get(source_name, 1.0)

            # Sort each source list by raw_score descending to establish ranks
            ranked = sorted(results, key=lambda r: r.raw_score, reverse=True)

            for rank, item in enumerate(ranked):
                rrf_score = weight / (self._k + rank + 1)
                rrf_scores[item.unified_id] = rrf_scores.get(item.unified_id, 0.0) + rrf_score

                if item.unified_id not in result_map:
                    result_map[item.unified_id] = item

        if not rrf_scores:
            return []

        # Normalize RRF scores to [0, 1] range
        # Max possible RRF score = sum of (weight / (k + 1)) for each source at rank 0
        max_rrf = sum(self._source_weights.get(src, 1.0) / (self._k + 1) for src in source_results)
        if max_rrf == 0:
            max_rrf = 1.0

        for uid, item in result_map.items():
            base_rrf = rrf_scores[uid] / max_rrf  # normalized to [0, 1]
            boost = normalizer.normalize(item, options)
            # Combine: RRF position as primary, raw_score quality as secondary
            # Weight: 60% RRF rank fusion + 40% original quality signal
            item.normalized_score = base_rrf
            item.final_score = 0.6 * base_rrf + 0.4 * boost

        # Sort by final RRF score
        merged = sorted(result_map.values(), key=lambda r: r.final_score, reverse=True)
        return merged


class Deduplicator:
    """Deduplicate results using content hashing."""

    def deduplicate(
        self,
        items: list[SearchResultItem],
    ) -> list[SearchResultItem]:
        seen_hashes: dict[str, SearchResultItem] = {}
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
        self,
        items: list[SearchResultItem],
        options: SearchOptions,
    ) -> list[SearchResultItem]:
        sorted_items = sorted(items, key=lambda x: x.final_score, reverse=True)

        if not options.diversity_enabled:
            return sorted_items

        # Ensure source diversity: don't let one source dominate top results
        reranked = []
        source_counts: dict[str, int] = {}
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

    def __init__(self, link_registry: LinkRegistry | None = None):
        self._registry = link_registry

    def enrich(
        self,
        items: list[SearchResultItem],
        max_depth: int = 1,
        min_strength: float = 0.5,
    ) -> list[SearchResultItem]:
        if not self._registry:
            return items

        for item in items:
            try:
                all_links = self._registry.get_all_links(item.unified_id, min_strength=min_strength)
                for link in all_links.get("outgoing", []):
                    item.linked_entities.append(
                        LinkedEntity(
                            target_id=link.target_id,
                            link_type=link.link_type.value,
                            strength=link.strength,
                            direction="outgoing",
                        )
                    )
                for link in all_links.get("incoming", []):
                    item.linked_entities.append(
                        LinkedEntity(
                            target_id=link.source_id,
                            link_type=link.link_type.value,
                            strength=link.strength,
                            direction="incoming",
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to enrich {item.unified_id}: {e}")

        return items


class UnifiedSearchEngine:
    """Orchestrates federated search across all memory subsystems.

    Pipeline: Parallel dispatch -> RRF Fusion -> Filter -> Dedup -> Rerank -> Enrich
    """

    def __init__(self, link_registry: LinkRegistry | None = None):
        self._adapters: dict[str, BaseSearchAdapter] = {}
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
        sources: list[SourceServer] | None = None,
        memory_types: list[MemoryType] | None = None,
        min_score: float = 0.3,
        limit: int = 20,
        include_links: bool = True,
        options: SearchOptions | None = None,
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

        # Collect results per source (needed for RRF)
        source_results: dict[str, list[SearchResultItem]] = {}
        sources_searched = []
        sources_failed = []

        # Hard ceiling: even if per-adapter wait_for misbehaves in a long-running
        # MCP session (thread pool exhaustion, event loop starvation), the whole
        # gather phase cannot exceed this bound. See cache/memory-orchestrator-timeout-bug-2026-04-23.md.
        hard_timeout = options.timeout_ms / 1000 * 1.5

        try:
            async with asyncio.timeout(hard_timeout):
                for name, task in tasks.items():
                    task_start = time.time()
                    try:
                        results = await task
                        source_results[name] = results
                        sources_searched.append(name)
                    except TimeoutError:
                        duration_ms = (time.time() - task_start) * 1000
                        sources_failed.append(
                            SourceError(source=name, error="timeout", duration_ms=duration_ms)
                        )
                        logger.warning(f"Search timeout for {name} ({duration_ms:.0f}ms)")
                    except Exception as e:
                        duration_ms = (time.time() - task_start) * 1000
                        sources_failed.append(
                            SourceError(source=name, error=str(e), duration_ms=duration_ms)
                        )
                        logger.error(f"Search error for {name}: {e}")
        except TimeoutError:
            for name, task in tasks.items():
                if name in source_results or any(e.source == name for e in sources_failed):
                    continue
                if task.done() and not task.cancelled() and task.exception() is None:
                    source_results[name] = task.result()
                    sources_searched.append(name)
                    continue
                if not task.done():
                    task.cancel()
                sources_failed.append(
                    SourceError(source=name, error="hard_timeout", duration_ms=hard_timeout * 1000)
                )
            logger.error(
                f"Search hard timeout after {hard_timeout:.1f}s; cancelled remaining adapters"
            )

        # Filter by memory type (per-source before fusion)
        if memory_types:
            type_values = {mt.value for mt in memory_types}
            source_results = {
                src: [r for r in results if r.memory_type.value in type_values]
                for src, results in source_results.items()
            }

        # Score fusion: RRF or legacy normalizer
        if options.rrf_enabled and len(source_results) > 0:
            rrf = RRFMerger(
                k=options.rrf_k,
                source_weights=options.rrf_source_weights,
            )
            all_results = rrf.fuse(source_results, options)
        else:
            # Fallback: flat merge + normalize
            all_results = [item for results in source_results.values() for item in results]
            for item in all_results:
                item.normalized_score = self._normalizer.normalize(item, options)
                item.final_score = item.normalized_score

        # Filter by min score
        all_results = [r for r in all_results if r.final_score >= min_score]

        # Deduplicate
        if options.dedup_enabled:
            all_results = self._deduplicator.deduplicate(all_results)

        # Rerank with diversity
        all_results = self._reranker.rerank(all_results, options)

        # Enrich with links
        if include_links:
            all_results = self._enricher.enrich(
                all_results,
                options.max_link_depth,
                options.min_link_strength,
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
            metadata={
                "options": {k: v for k, v in options.__dict__.items() if not callable(v)},
                "fusion": "rrf" if options.rrf_enabled else "normalize",
            },
        )


# Global engine instance
_global_engine: UnifiedSearchEngine | None = None


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
    sources: list[SourceServer] | None = None,
    memory_types: list[MemoryType] | None = None,
    min_score: float = 0.3,
    limit: int = 20,
    include_links: bool = True,
    search_options: SearchOptions | None = None,
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
