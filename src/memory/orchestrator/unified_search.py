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

# Whole-gather ceiling as a multiple of the per-adapter timeout. >1 by design: every
# arm should resolve via its own wait_for (at 1.0x) and this is only the backstop.
# A module constant rather than a literal so the backstop itself can be driven in a
# test (set it <1 and the ceiling wins the race deterministically) — see
# resolve_after_hard_timeout on why the real-world trigger cannot be simulated.
HARD_TIMEOUT_FACTOR = 1.5


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
    # Coarse machine-readable cause (roadmap 260716 P1.3): "timeout" / "hard_timeout" /
    # "circuit_open" / the exception class name. `error` carries the human message and
    # is unstable across libraries; this is what the trace log groups by.
    error_type: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "error": self.error,
            "error_type": self.error_type,
            "duration_ms": self.duration_ms,
        }


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


def _circuit_is_open(breaker: Any) -> bool:
    """True only for a genuinely OPEN circuit — HALF_OPEN must be allowed to probe.

    Deliberately NOT a bare ``allow_request()``, which is the API this file would
    otherwise reach for. Measured on the shared CircuitBreaker: in HALF_OPEN it returns
    ``success_count < half_open_max_probes`` where ``success_count`` is a LIFETIME
    counter that nothing resets (``_transition_to`` clears only failure_count /
    consecutive_successes, and ``_transition_to(HALF_OPEN)`` has no caller at all). So
    an arm with any successful history is denied every probe forever once tripped, and
    ``record_success`` — which tests the raw ``_stats.state``, never HALF_OPEN — can
    never close the circuit back.

    That would make a transient TEI restart a PERMANENT outage of the semantic arm
    (until /mcp reconnect), which is strictly worse than the slow arm P1.3 set out to
    fix. Mirroring ``call_async`` (reject only on raw OPEN) bounds the damage to
    reset_timeout and keeps this consumer identical to propagation's.

    The underlying HALF_OPEN state machine is broken for every consumer — reported in
    roadmap 260716 §3.3, not fixed here: it is shared infrastructure and predates P1.
    """
    from ..infrastructure.circuit_breaker import CircuitState

    if breaker.state is not CircuitState.OPEN:
        return False
    breaker.allow_request()  # bookkeeping only: counts the rejection for circuit_status
    return True


def resolve_after_hard_timeout(
    name: str, task: Any, hard_timeout_s: float
) -> tuple[list[SearchResultItem] | None, SourceError | None]:
    """Reap a task the gather phase never got to await. Exactly one half is non-None.

    Split out of the hard-timeout handler so the DECISION can be pinned without
    simulating the timing that leads to it (roadmap 260716 M2).

    The decision itself: a task that already finished with a REAL error (TEI refused,
    Qdrant 400, a bad payload) reports THAT error. It used to be relabelled
    ``hard_timeout`` merely because the gather phase ran out of budget — the true cause
    was destroyed on the way to the caller, and the operator went looking at latency.

    ⚠ Reachability (measured 2026-07-17): the branch is a backstop for the case its
    caller's comment names — "per-adapter wait_for misbehaves" — but a coroutine that
    swallows CancelledError defeats the outer ``asyncio.timeout`` exactly as it defeats
    ``wait_for`` (probe: 1.03 s elapsed against a 0.15 s ceiling, no TimeoutError). With
    well-behaved adapters every arm resolves by 1.0x the per-adapter timeout, i.e. before
    the 1.5x ceiling. So this fires only under loop starvation from OUTSIDE the engine.
    """
    if task.done() and not task.cancelled():
        exc = task.exception()
        if exc is None:
            return (task.result(), None)
        return (
            None,
            SourceError(
                source=name,
                error=str(exc),
                duration_ms=hard_timeout_s * 1000,
                error_type=type(exc).__name__,
            ),
        )
    if not task.done():
        task.cancel()
    return (
        None,
        SourceError(
            source=name,
            error="hard_timeout",
            duration_ms=hard_timeout_s * 1000,
            error_type="hard_timeout",
        ),
    )


def _naive(dt: datetime) -> datetime:
    """Drop tzinfo (converting to local time first) so a date can be compared to now().

    roadmap 260716 M9: every adapter is free to produce an aware datetime, but this
    engine's arithmetic is naive-local. Subtracting the two raises
    ``TypeError: can't subtract offset-naive and offset-aware datetimes`` — and it
    raises in ScoreNormalizer, i.e. AFTER the arms have been collected, outside the
    per-adapter isolation. One aware date anywhere would take down the whole federated
    search. The live data is naive today; this is the mine, defused.
    """
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo is not None else dt


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
            age = datetime.now() - _naive(item.created_at)
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
        # Max possible RRF score = sum of (weight / (k + 1)) for each CONTRIBUTING
        # source at rank 0.
        #
        # roadmap 260716 M1: sources that returned nothing are excluded, like sources
        # that failed. Failed arms never reach this dict (they go to sources_failed),
        # so counting empty ones was an asymmetry with a real cost: with three arms
        # registered and only one producing a hit, that hit's normalized base was
        # 1/3 ≈ 0.33 — grazing the default min_score=0.3 — purely because two arms had
        # nothing to say. An arm that says nothing is not evidence against a result.
        max_rrf = sum(
            self._source_weights.get(src, 1.0) / (self._k + 1)
            for src, results in source_results.items()
            if results
        )
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

    def __init__(
        self,
        link_registry: LinkRegistry | None = None,
        breaker_registry: Any = None,
    ):
        self._adapters: dict[str, BaseSearchAdapter] = {}
        self._normalizer = ScoreNormalizer()
        self._deduplicator = Deduplicator()
        self._reranker = Reranker()
        self._enricher = LinkEnricher(link_registry)
        # roadmap 260716 P1.3: optional CircuitBreakerRegistry, shared with the
        # orchestrator so search arms get named breakers "search:<source>" — the
        # symmetry propagation already had ("propagation:<source>"). Without it a dead
        # TEI cost every single search the full per-adapter timeout, forever.
        # None (the default) keeps the engine standalone and breaker-free.
        self._breaker_registry = breaker_registry

    def _breaker(self, source: str) -> Any:
        """Named breaker for a search arm, or None when no registry is wired."""
        if self._breaker_registry is None:
            return None
        try:
            from ..infrastructure.circuit_breaker import CircuitBreakerConfig

            return self._breaker_registry.get_or_create(
                f"search:{source}",
                CircuitBreakerConfig(failure_threshold=5, reset_timeout=60.0),
            )
        except Exception:  # registry misconfigured → search must not die for it
            logger.warning("search breaker unavailable for %s", source, exc_info=True)
            return None

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

        # Collect results per source (needed for RRF)
        source_results: dict[str, list[SearchResultItem]] = {}
        sources_searched: list[str] = []
        sources_failed: list[SourceError] = []

        # Run searches in parallel with timeout.
        # The breaker is consulted BEFORE the coroutine exists: wrapping an
        # already-created `wait_for(adapter.search(...))` in breaker.call_async would,
        # on an OPEN circuit, close the outer coroutine and leave the inner
        # adapter.search() never awaited (RuntimeWarning). allow_request() is the sync
        # API for exactly this position.
        tasks = {}
        breakers: dict[str, Any] = {}
        for name, adapter in adapters.items():
            breaker = self._breaker(name)
            if breaker is not None and _circuit_is_open(breaker):
                # Fail fast and HONESTLY: a tripped arm is a reported failure, never a
                # silent empty arm (that would read as "nothing matched").
                sources_failed.append(
                    SourceError(
                        source=name,
                        error=f"circuit 'search:{name}' is OPEN",
                        duration_ms=0.0,
                        error_type="circuit_open",
                    )
                )
                logger.warning("Search arm %s skipped — circuit OPEN", name)
                continue
            breakers[name] = breaker
            tasks[name] = asyncio.create_task(
                asyncio.wait_for(
                    adapter.search(query, limit=limit),
                    timeout=options.timeout_ms / 1000,
                )
            )

        # Hard ceiling: even if per-adapter wait_for misbehaves in a long-running
        # MCP session (thread pool exhaustion, event loop starvation), the whole
        # gather phase cannot exceed this bound. See cache/memory-orchestrator-timeout-bug-2026-04-23.md.
        hard_timeout = options.timeout_ms / 1000 * HARD_TIMEOUT_FACTOR

        def _record(name: str, ok: bool, err: str = "") -> None:
            """Feed the arm's outcome back to its breaker (no-op without a registry)."""
            breaker = breakers.get(name)
            if breaker is None:
                return
            try:
                breaker.record_success() if ok else breaker.record_failure(err)
            except Exception:  # bookkeeping must never fail a search
                logger.debug("breaker bookkeeping failed for %s", name, exc_info=True)

        try:
            async with asyncio.timeout(hard_timeout):
                for name, task in tasks.items():
                    task_start = time.time()
                    try:
                        results = await task
                        source_results[name] = results
                        sources_searched.append(name)
                        _record(name, True)
                    except TimeoutError:
                        duration_ms = (time.time() - task_start) * 1000
                        sources_failed.append(
                            SourceError(
                                source=name,
                                error="timeout",
                                duration_ms=duration_ms,
                                error_type="timeout",
                            )
                        )
                        _record(name, False, "timeout")
                        logger.warning(f"Search timeout for {name} ({duration_ms:.0f}ms)")
                    except Exception as e:
                        duration_ms = (time.time() - task_start) * 1000
                        sources_failed.append(
                            SourceError(
                                source=name,
                                error=str(e),
                                duration_ms=duration_ms,
                                error_type=type(e).__name__,
                            )
                        )
                        _record(name, False, str(e))
                        logger.error(f"Search error for {name}: {e}")
        except TimeoutError:
            for name, task in tasks.items():
                if name in source_results or any(e.source == name for e in sources_failed):
                    continue
                results, err = resolve_after_hard_timeout(name, task, hard_timeout)
                if err is None:
                    source_results[name] = results or []
                    sources_searched.append(name)
                    _record(name, True)
                else:
                    sources_failed.append(err)
                    _record(name, False, err.error)
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

        # §27 P1 D1.2: persist the federated-read trace (per-source hits, latency,
        # outcome) — metadata-only (query text NOT logged), fail-soft.
        try:
            from ..infrastructure.trace_log import write_trace

            write_trace(
                "memory-read.log",
                "search",
                disable_env="MEMORY_READ_LOG_DISABLE",
                query_len=len(query),
                arm_hits={src: len(res) for src, res in source_results.items()},
                sources_searched=sources_searched,
                sources_failed=[e.source for e in sources_failed],
                # roadmap 260716 M3: names alone made the trace useless for triage —
                # "vector-memory failed" could be TEI down, a Qdrant 400 or a tripped
                # breaker, and the log could not tell them apart.
                sources_failed_detail={e.source: e.error_type for e in sources_failed},
                final=len(all_results),
                min_score=min_score,
                rrf=options.rrf_enabled,
                latency_ms=round(elapsed_ms, 1),
            )
        except Exception:
            pass

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
