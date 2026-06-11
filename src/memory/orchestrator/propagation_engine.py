"""
Propagation Engine — Confidence/Importance propagation across memory systems.

BFS-based graph traversal with:
- Event-driven propagation via asyncio.Queue
- Rate limiting (depth, entity count, delta threshold)
- Time and distance decay
- Circuit breaker protection
- Async background processing

Migrated from: memory-orchestrator/src/propagation_engine.py (631 lines)
Changes from source:
- Replaced external CircuitBreaker import with infrastructure.circuit_breaker
- UnifiedID/LinkRegistry imports are local (same package)
- No Neo4j dependency (LinkRegistry is already SQLite-backed)

Version: 2.0 (2026-04-04) — P1 migration
"""

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ..infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
)
from .link_registry import LinkType
from .unified_id import SourceServer, UnifiedID

if TYPE_CHECKING:
    from .link_registry import LinkRegistry

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class PropagationConfig:
    """Configuration for propagation engine."""

    # Rate limiting
    max_depth: int = 3
    max_entities_per_event: int = 10
    min_delta_threshold: float = 0.001  # 0.1%

    # Decay factors
    enable_time_decay: bool = True
    time_decay_days: int = 365
    min_decay_factor: float = 0.5

    enable_distance_decay: bool = True
    distance_decay_per_level: float = 0.5
    min_distance_decay: float = 0.3

    # Event processing
    event_queue_size: int = 1000
    enable_event_deduplication: bool = True

    # Background processing
    enable_background_processing: bool = True
    background_workers: int = 2

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0


# =============================================================================
# Events and Results
# =============================================================================


@dataclass
class PropagationEvent:
    """Event triggering propagation."""

    event_id: str
    entity_id: str  # UnifiedID string
    base_delta: float
    success: bool  # True = boost, False = penalty
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.event_id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, PropagationEvent):
            return False
        return self.event_id == other.event_id


@dataclass
class PropagationResult:
    """Result of propagation operation."""

    event_id: str
    source_entity_id: str
    entities_updated: list[str]
    updates_applied: dict[str, float]
    cascades_prevented: int
    final_depth: int
    processing_time_ms: float
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_entity_id": self.source_entity_id,
            "entities_updated": self.entities_updated,
            "updates_applied": self.updates_applied,
            "cascades_prevented": self.cascades_prevented,
            "final_depth": self.final_depth,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }

    def __str__(self) -> str:
        return (
            f"PropagationResult(updated={len(self.entities_updated)}, "
            f"prevented={self.cascades_prevented}, depth={self.final_depth})"
        )


# =============================================================================
# Directional Propagation Rules
# =============================================================================

FORWARD_PROPAGATION_LINKS = {
    LinkType.BASED_ON,
    LinkType.SUPPORTS,
    LinkType.CONTRADICTS,
    LinkType.EXTENDS,
    LinkType.DERIVES_FROM,
}

REVERSE_PROPAGATION_LINKS = {
    LinkType.SUPPORTS,
    LinkType.CONTRADICTS,
    LinkType.EXTENDS,
}

RECEIVER_TYPES = {
    ("vector-memory", "semantic"),
    ("memory-ai", "episodic"),
}

STATIC_TYPES = {
    ("1c-docs-rag", "docs"),
    ("conv-memory", "episodic"),
}


# =============================================================================
# Main Engine
# =============================================================================


class PropagationEngine:
    """
    Engine for propagating confidence/importance changes across linked entities.

    Features:
    - Event-driven propagation with asyncio.Queue
    - BFS-based graph traversal via LinkRegistry (SQLite)
    - Rate limiting (depth, entity count, delta threshold)
    - Time and distance decay
    - Circuit breaker protection
    - Async background processing

    Usage:
        engine = PropagationEngine(link_registry, config)
        await engine.start()

        result = await engine.propagate(
            entity_id="semantic:vector-memory:abc123",
            base_delta=0.02,
            success=True
        )

        await engine.stop()
    """

    def __init__(
        self,
        link_registry: "LinkRegistry",  # type: ignore[name-defined]
        config: PropagationConfig | None = None,
        update_handlers: dict[SourceServer, Callable] | None = None,
    ):
        self.link_registry = link_registry
        self.config = config or PropagationConfig()
        self.update_handlers = update_handlers or {}

        # Circuit breaker
        self._circuit_breaker: CircuitBreaker | None = None
        if self.config.circuit_breaker_enabled:
            self._circuit_breaker = CircuitBreaker(
                name="propagation_engine",
                config=CircuitBreakerConfig(
                    failure_threshold=self.config.circuit_breaker_threshold,
                    reset_timeout=self.config.circuit_breaker_timeout,
                ),
            )

        # Event queue
        self._event_queue: asyncio.Queue[PropagationEvent] | None = None
        self._recent_events: set[str] = set()

        # Background tasks
        self._worker_tasks: list[asyncio.Task] = []
        self._running = False

        # Statistics
        self._stats = {
            "events_processed": 0,
            "entities_updated": 0,
            "cascades_prevented": 0,
            "total_processing_time_ms": 0.0,
        }

        logger.info(
            "PropagationEngine initialized (depth=%d, workers=%d)",
            self.config.max_depth,
            self.config.background_workers,
        )

    async def start(self):
        """Start background event processing."""
        if self._running:
            return

        self._running = True
        self._event_queue = asyncio.Queue(maxsize=self.config.event_queue_size)

        if self.config.enable_background_processing:
            for i in range(self.config.background_workers):
                task = asyncio.create_task(self._worker(f"worker-{i}"))
                self._worker_tasks.append(task)
            logger.info("PropagationEngine started with %d workers", self.config.background_workers)

    async def stop(self):
        """Stop background event processing."""
        if not self._running:
            return

        self._running = False
        for task in self._worker_tasks:
            task.cancel()
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        logger.info("PropagationEngine stopped")

    async def propagate(
        self,
        entity_id: str,
        base_delta: float,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> PropagationResult:
        """
        Propagate confidence/importance change through graph.

        Args:
            entity_id: Source entity UnifiedID string
            base_delta: Change magnitude (positive = boost, negative = penalty)
            success: True if pattern applied successfully (boost direction)
            metadata: Optional event metadata

        Returns:
            PropagationResult with updated entities and statistics
        """
        event = PropagationEvent(
            event_id=str(uuid4()),
            entity_id=entity_id,
            base_delta=base_delta,
            success=success,
            metadata=metadata or {},
        )

        # Deduplication
        if self.config.enable_event_deduplication:
            if event.entity_id in self._recent_events:
                return self._skip_result(event, "duplicate_event")
            self._recent_events.add(event.entity_id)
            # Keep recent set bounded
            if len(self._recent_events) > 1000:
                self._recent_events.clear()

        # Queue for background or process directly
        if self.config.enable_background_processing and self._event_queue is not None:
            try:
                await asyncio.wait_for(self._event_queue.put(event), timeout=1.0)
                return PropagationResult(
                    event_id=event.event_id,
                    source_entity_id=entity_id,
                    entities_updated=[],
                    updates_applied={},
                    cascades_prevented=0,
                    final_depth=0,
                    processing_time_ms=0,
                    reason="queued_for_background_processing",
                )
            except TimeoutError:
                logger.warning("Event queue full, processing synchronously")

        # Process with circuit breaker protection
        if self._circuit_breaker is not None:
            coro = self._process_propagation(event)
            try:
                result = await self._circuit_breaker.call_async(coro)
            except CircuitBreakerError as e:
                # coro already closed by call_async when circuit is OPEN
                logger.warning("Circuit OPEN — propagation blocked for %s: %s", entity_id, e)
                return self._skip_result(event, "circuit_breaker_open")
        else:
            result = await self._process_propagation(event)

        # Update stats
        self._stats["events_processed"] += 1
        self._stats["entities_updated"] += len(result.entities_updated)
        self._stats["cascades_prevented"] += result.cascades_prevented
        self._stats["total_processing_time_ms"] += result.processing_time_ms

        return result

    async def _worker(self, worker_name: str):
        """Background worker for processing events."""
        logger.debug("Worker %s started", worker_name)
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                result = await self._process_propagation(event)
                if self._event_queue is not None:
                    self._event_queue.task_done()

                self._stats["events_processed"] += 1
                self._stats["entities_updated"] += len(result.entities_updated)
                self._stats["cascades_prevented"] += result.cascades_prevented

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker %s error: %s", worker_name, e)

    async def _process_propagation(self, event: PropagationEvent) -> PropagationResult:
        """BFS propagation through linked entities."""
        start_time = datetime.now()

        try:
            # Parse source entity
            try:
                UnifiedID.parse(event.entity_id)
            except ValueError:
                return self._error_result(event, "invalid_entity_id")

            # BFS traversal
            entities_updated: list[str] = []
            updates_applied: dict[str, float] = {}
            cascades_prevented = 0
            max_depth_seen = 0

            queue: deque[tuple[str, float, int]] = deque([(event.entity_id, event.base_delta, 0)])
            visited: set[str] = {event.entity_id}

            while queue:
                current_id, current_delta, depth = queue.popleft()
                max_depth_seen = max(max_depth_seen, depth)

                if depth >= self.config.max_depth:
                    cascades_prevented += 1
                    continue

                # Get outgoing links via SQLite-backed LinkRegistry
                try:
                    links = self.link_registry.get_links_from(current_id)
                except Exception as e:
                    logger.error("Error getting links from %s: %s", current_id, e)
                    continue

                for link in links:
                    if not self._can_receive_propagation(link.target_id):
                        continue

                    new_delta = self._calculate_delta(
                        current_delta, link.strength, depth + 1, link.created_at
                    )

                    if abs(new_delta) < self.config.min_delta_threshold:
                        cascades_prevented += 1
                        continue

                    if len(entities_updated) >= self.config.max_entities_per_event:
                        cascades_prevented += 1
                        continue

                    if await self._apply_update(link.target_id, new_delta):
                        entities_updated.append(link.target_id)
                        updates_applied[link.target_id] = new_delta

                        if link.target_id not in visited:
                            visited.add(link.target_id)
                            queue.append((link.target_id, new_delta, depth + 1))

            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            result = PropagationResult(
                event_id=event.event_id,
                source_entity_id=event.entity_id,
                entities_updated=entities_updated,
                updates_applied=updates_applied,
                cascades_prevented=cascades_prevented,
                final_depth=max_depth_seen,
                processing_time_ms=elapsed,
            )
            # §27 P1 D1.3: persist propagation reach/decay outcome — metadata-only, fail-soft.
            try:
                from ..infrastructure.trace_log import write_trace

                write_trace(
                    "memory-propagation.log",
                    "propagate",
                    disable_env="MEMORY_PROPAGATION_LOG_DISABLE",
                    source=event.entity_id,
                    entities_updated=len(entities_updated),
                    cascades_prevented=cascades_prevented,
                    final_depth=max_depth_seen,
                    latency_ms=round(elapsed, 1),
                )
            except Exception:
                pass
            return result

        except Exception as e:
            logger.error("Propagation error: %s", e)
            return self._error_result(event, str(e))

    def _can_receive_propagation(self, entity_id: str) -> bool:
        """Check if entity can receive propagation updates."""
        try:
            uid = UnifiedID.parse(entity_id)
            entity_type = (uid.source.value, uid.memory_type.value)
            if entity_type in RECEIVER_TYPES:
                return True
            if entity_type in STATIC_TYPES:
                return False
            # Unknown type — conservative
            return False
        except Exception:
            return False

    def _calculate_delta(
        self,
        base_delta: float,
        link_strength: float,
        depth: int,
        link_created_at: datetime | None,
    ) -> float:
        """Calculate propagated delta with decay factors."""
        delta = base_delta * link_strength

        # Time decay
        if self.config.enable_time_decay and link_created_at:
            days_since = (datetime.now() - link_created_at).days
            time_decay = max(
                self.config.min_decay_factor,
                1.0 - (days_since / self.config.time_decay_days),
            )
            delta *= time_decay

        # Distance decay (exponential)
        if self.config.enable_distance_decay:
            distance_decay = max(
                self.config.min_distance_decay,
                self.config.distance_decay_per_level**depth,
            )
            delta *= distance_decay

        return delta

    async def _apply_update(self, entity_id: str, delta: float) -> bool:
        """Apply update to entity via registered handler.

        Honest semantics (roadmap 260609 P2.3): an update is counted *only* when
        a handler is registered for the entity's source **and** that handler
        reports a real mutation (truthy return). With no handler the engine
        cannot mutate anything, so it returns ``False`` instead of fabricating
        success — callers therefore never see phantom ``entities_updated``.

        In production the orchestrator wires real handlers
        (``MemoryOrchestrator._build_propagation_handlers``: vector-memory Beta
        succ/fail nudge + memory-ai importance nudge). A handler-less engine
        (e.g. an isolated unit test of the BFS/decay machinery) reports zero
        updates unless the test supplies its own handlers.
        """
        try:
            uid = UnifiedID.parse(entity_id)
            handler = self.update_handlers.get(uid.source)
            if handler is None:
                logger.debug("No update handler for %s; not counting as updated", entity_id)
                return False
            return bool(await handler(entity_id, delta))
        except Exception as e:
            logger.error("Error applying update to %s: %s", entity_id, e)
            return False

    def _error_result(self, event: PropagationEvent, reason: str) -> PropagationResult:
        return PropagationResult(
            event_id=event.event_id,
            source_entity_id=event.entity_id,
            entities_updated=[],
            updates_applied={},
            cascades_prevented=0,
            final_depth=0,
            processing_time_ms=0,
            reason=f"error: {reason}",
        )

    def _skip_result(self, event: PropagationEvent, reason: str) -> PropagationResult:
        return PropagationResult(
            event_id=event.event_id,
            source_entity_id=event.entity_id,
            entities_updated=[],
            updates_applied={},
            cascades_prevented=0,
            final_depth=0,
            processing_time_ms=0,
            reason=reason,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get propagation statistics."""
        stats = self._stats.copy()
        if self._circuit_breaker:
            stats["circuit_breaker"] = self._circuit_breaker.stats
        return stats

    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            "events_processed": 0,
            "entities_updated": 0,
            "cascades_prevented": 0,
            "total_processing_time_ms": 0.0,
        }


# =============================================================================
# Convenience function
# =============================================================================


async def propagate_update(
    entity_id: str,
    base_delta: float,
    link_registry: "LinkRegistry",
    config: PropagationConfig | None = None,
    update_handlers: "dict[SourceServer, Callable] | None" = None,
) -> PropagationResult:
    """One-shot propagation without managing engine lifecycle.

    Pass ``update_handlers`` to actually mutate the backing stores; without
    them the engine reports zero updates (honest, roadmap 260609 P2.3) rather
    than simulating success.
    """
    engine = PropagationEngine(link_registry, config, update_handlers=update_handlers)
    return await engine.propagate(entity_id, base_delta)


__all__ = [
    "PropagationEngine",
    "PropagationConfig",
    "PropagationEvent",
    "PropagationResult",
    "propagate_update",
    "FORWARD_PROPAGATION_LINKS",
    "REVERSE_PROPAGATION_LINKS",
    "RECEIVER_TYPES",
    "STATIC_TYPES",
]
