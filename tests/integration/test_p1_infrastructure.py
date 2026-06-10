"""
Integration tests for P1: Infrastructure and Propagation.

Tests:
- CircuitBreaker: state transitions, decorator, registry
- PropagationEngine: BFS traversal, decay, rate limiting
- AuditService: log, query, cleanup
- BaseMemoryAdapter: abstract interface
- PatternMerger: deduplication, conflict resolution
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.memory.ai_memory.adapters.base import (
    BackendStats,
    BaseMemoryAdapter,
    SaveRequest,
    SearchResult,
)
from src.memory.ai_memory.services.audit_service import (
    AuditAction,
    AuditQuery,
    AuditService,
)
from src.memory.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
)
from src.memory.orchestrator.link_registry import LinkRegistry, LinkType
from src.memory.orchestrator.propagation_engine import (
    PropagationConfig,
    PropagationEngine,
)
from src.memory.orchestrator.unified_id import SourceServer
from src.memory.skill_learning.merge_patterns import (
    ConflictStrategy,
    PatternMerger,
)


async def _always_apply(entity_id: str, delta: float) -> bool:
    """Dummy update handler that reports a successful mutation.

    Roadmap 260609 P2.3 made ``PropagationEngine._apply_update`` honest: with no
    handler it returns False (no fabricated updates). Tests that exercise the
    BFS/decay/rate-limit machinery itself supply this handler so traversal
    proceeds and ``entities_updated`` reflects real (here, stubbed) writes.
    """
    return True


# Handlers for the two receiver source types used in these tests.
_TEST_HANDLERS = {
    SourceServer.VECTOR_MEMORY: _always_apply,
    SourceServer.MEMORY_AI: _always_apply,
}

# =============================================================================
# CircuitBreaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_under_threshold(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        cb.record_failure("err1")
        cb.record_failure("err2")
        assert cb.state == CircuitState.CLOSED

    def test_transitions_to_open_at_threshold(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        for i in range(3):
            cb.record_failure(f"err{i}")
        assert cb.state == CircuitState.OPEN

    def test_open_rejects_requests(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure("err")
        assert not cb.allow_request()

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        cb.record_failure("err1")
        cb.record_failure("err2")
        cb.record_success()
        cb.record_failure("err3")  # failure_count was reset to 0 by success
        assert cb.state == CircuitState.CLOSED  # only 1 failure, not 3

    def test_reset_forces_closed(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure("err")
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_decorator_wraps_async(self):
        cb = CircuitBreaker("test")

        @cb
        async def good():
            return 42

        result = await good()
        assert result == 42

    @pytest.mark.asyncio
    async def test_call_async_rejects_when_open(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure("err")
        with pytest.raises(CircuitBreakerError):
            await cb.call_async(asyncio.sleep(0))

    def test_stats_snapshot(self):
        cb = CircuitBreaker("test")
        cb.record_success()
        stats = cb.stats
        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["total_calls"] == 1


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""

    def test_get_or_create(self):
        reg = CircuitBreakerRegistry()
        cb1 = reg.get_or_create("svc1")
        cb2 = reg.get_or_create("svc1")
        assert cb1 is cb2

    def test_get_all_stats(self):
        reg = CircuitBreakerRegistry()
        reg.get_or_create("a")
        reg.get_or_create("b")
        stats = reg.get_all_stats()
        assert "a" in stats
        assert "b" in stats

    def test_reset_all(self):
        reg = CircuitBreakerRegistry()
        cb = reg.get_or_create("svc")
        cb.record_failure("e")
        cb.record_failure("e")
        cb.record_failure("e")
        cb.record_failure("e")
        cb.record_failure("e")
        reg.reset_all()
        assert cb.state == CircuitState.CLOSED


# =============================================================================
# PropagationEngine Tests
# =============================================================================


class TestPropagationEngine:
    """Test BFS propagation with decay."""

    @pytest.fixture
    def db_path(self, tmp_path):
        return str(tmp_path / "links.db")

    @pytest.fixture
    def link_registry(self, db_path):
        return LinkRegistry(db_path=db_path)

    @pytest.mark.asyncio
    async def test_propagate_no_links(self, link_registry):
        engine = PropagationEngine(
            link_registry,
            PropagationConfig(enable_background_processing=False),
        )
        result = await engine.propagate("semantic:vector-memory:abc", 0.1)
        assert result.entities_updated == []
        assert result.reason == ""

    @pytest.mark.asyncio
    async def test_propagate_through_links(self, link_registry):
        # Create linked entities
        link_registry.create_link(
            "semantic:vector-memory:a",
            "semantic:vector-memory:b",
            LinkType.SUPPORTS,
            strength=0.8,
        )
        link_registry.create_link(
            "semantic:vector-memory:b",
            "episodic:memory-ai:c",
            LinkType.BASED_ON,
            strength=0.6,
        )

        engine = PropagationEngine(
            link_registry,
            PropagationConfig(enable_background_processing=False, max_depth=3),
        )
        result = await engine.propagate("semantic:vector-memory:a", 0.1)
        assert len(result.entities_updated) >= 1
        assert result.final_depth >= 1

    @pytest.mark.asyncio
    async def test_depth_limit(self, link_registry):
        # Create a chain of 5 links
        ids = [f"semantic:vector-memory:{i}" for i in range(6)]
        for i in range(5):
            link_registry.create_link(
                ids[i],
                ids[i + 1],
                LinkType.EXTENDS,
                strength=0.9,
            )

        engine = PropagationEngine(
            link_registry,
            PropagationConfig(
                enable_background_processing=False,
                max_depth=2,
                distance_decay_per_level=1.0,  # no distance decay
                enable_time_decay=False,
            ),
        )
        result = await engine.propagate(ids[0], 0.1)
        assert result.final_depth <= 2

    @pytest.mark.asyncio
    async def test_delta_threshold(self, link_registry):
        link_registry.create_link(
            "semantic:vector-memory:a",
            "semantic:vector-memory:b",
            LinkType.SUPPORTS,
            strength=0.001,
        )

        engine = PropagationEngine(
            link_registry,
            PropagationConfig(
                enable_background_processing=False,
                min_delta_threshold=0.01,
                enable_time_decay=False,
                enable_distance_decay=False,
            ),
        )
        result = await engine.propagate("semantic:vector-memory:a", 0.001)
        # Delta too small (0.001 * 0.001 = 0.000001 < 0.01)
        assert result.cascades_prevented >= 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_protection(self, link_registry):
        config = PropagationConfig(
            enable_background_processing=False,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=1,
        )
        engine = PropagationEngine(link_registry, config)
        # Trip the circuit breaker
        engine._circuit_breaker.record_failure("err")
        assert engine._circuit_breaker.state == CircuitState.OPEN

        result = await engine.propagate("semantic:vector-memory:a", 0.1)
        assert result.reason == "circuit_breaker_open"

    def test_calculate_delta_with_decay(self, link_registry):
        engine = PropagationEngine(
            link_registry,
            PropagationConfig(enable_distance_decay=False, enable_time_decay=False),
        )
        # No decay at all
        delta = engine._calculate_delta(0.1, 0.8, 1, datetime.now())
        assert abs(delta - 0.08) < 0.001

    def test_calculate_delta_time_decay(self, link_registry):
        engine = PropagationEngine(
            link_registry,
            PropagationConfig(enable_distance_decay=False),
        )
        old_date = datetime.now() - timedelta(days=180)
        delta = engine._calculate_delta(0.1, 1.0, 0, old_date)
        assert delta < 0.1  # should be decayed

    @pytest.mark.asyncio
    async def test_background_processing(self, link_registry):
        engine = PropagationEngine(
            link_registry,
            PropagationConfig(
                enable_background_processing=True,
                background_workers=1,
                event_queue_size=10,
            ),
        )
        await engine.start()
        result = await engine.propagate("semantic:vector-memory:x", 0.1)
        assert result.reason == "queued_for_background_processing"
        await engine.stop()

    def test_stats(self, link_registry):
        engine = PropagationEngine(link_registry)
        stats = engine.get_stats()
        assert "events_processed" in stats


# =============================================================================
# AuditService Tests
# =============================================================================


class TestAuditService:
    """Test audit logging service."""

    @pytest.fixture
    def audit_dir(self, tmp_path):
        return tmp_path / "audit"

    @pytest.mark.asyncio
    async def test_log_and_query(self, audit_dir):
        svc = AuditService(storage_path=audit_dir / "audit.jsonl")
        entry = await svc.log(
            action=AuditAction.CREATE,
            resource_type="pattern",
            resource_id="abc123",
        )
        assert entry.id
        assert entry.action == AuditAction.CREATE

        results = await svc.query(AuditQuery(resource_type="pattern"))
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_recent(self, audit_dir):
        svc = AuditService(storage_path=audit_dir / "audit.jsonl")
        for i in range(5):
            await svc.log(action=AuditAction.SEARCH, resource_type="memory")
        recent = await svc.get_recent(limit=3)
        assert len(recent) == 3

    @pytest.mark.asyncio
    async def test_get_errors(self, audit_dir):
        svc = AuditService(storage_path=audit_dir / "audit.jsonl")
        await svc.log(action=AuditAction.CREATE, resource_type="x", success=True)
        await svc.log(
            action=AuditAction.DELETE, resource_type="y", success=False, error_message="not found"
        )
        # Flush so buffer is clear and only persisted entries remain
        await svc.flush()
        errors = await svc.get_errors()
        assert len(errors) == 1
        assert errors[0].error_message == "not found"

    @pytest.mark.asyncio
    async def test_stats(self, audit_dir):
        svc = AuditService(storage_path=audit_dir / "audit.jsonl")
        await svc.log(action=AuditAction.CREATE, resource_type="a")
        await svc.log(action=AuditAction.UPDATE, resource_type="b", success=False)
        stats = await svc.get_stats()
        assert stats["total_entries"] == 2
        assert stats["error_count"] == 1

    @pytest.mark.asyncio
    async def test_persistence(self, audit_dir):
        path = audit_dir / "audit.jsonl"
        svc1 = AuditService(storage_path=path)
        await svc1.log(action=AuditAction.CREATE, resource_type="test")
        await svc1.flush()

        svc2 = AuditService(storage_path=path)
        results = await svc2.query(AuditQuery(resource_type="test"))
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_cleanup(self, audit_dir):
        svc = AuditService(storage_path=audit_dir / "audit.jsonl", retention_days=0)
        await svc.log(action=AuditAction.CREATE, resource_type="old")
        await svc.flush()
        removed = await svc.cleanup()
        assert removed >= 1

    @pytest.mark.asyncio
    async def test_immediate_persist_for_destructive(self, audit_dir):
        path = audit_dir / "audit.jsonl"
        svc = AuditService(storage_path=path)
        await svc.log(action=AuditAction.DELETE, resource_type="critical")
        # DELETE should be immediately persisted
        assert path.exists()
        with open(path) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 1


# =============================================================================
# BaseMemoryAdapter Tests
# =============================================================================


class ConcreteAdapter(BaseMemoryAdapter):
    """Concrete implementation for testing."""

    def __init__(self):
        super().__init__({"enabled": True, "timeout": 5})
        self._store: dict = {}

    async def save(self, request: SaveRequest) -> str | None:
        import uuid

        eid = str(uuid.uuid4())
        self._store[eid] = {"content": request.content, **request.metadata}
        return eid

    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResult]:
        results = []
        for eid, data in self._store.items():
            if query.lower() in data.get("content", "").lower():
                results.append(
                    SearchResult(
                        content=data["content"],
                        score=0.8,
                        source="test",
                        entity_id=eid,
                    )
                )
        return results[:limit]

    async def get(self, entity_id: str) -> dict | None:
        return self._store.get(entity_id)

    async def delete(self, entity_id: str) -> bool:
        if entity_id in self._store:
            del self._store[entity_id]
            return True
        return False

    async def update(self, entity_id: str, updates: dict) -> bool:
        if entity_id in self._store:
            self._store[entity_id].update(updates)
            return True
        return False

    async def get_stats(self) -> BackendStats:
        return BackendStats(
            backend_name="test",
            status="healthy",
            total_items=len(self._store),
        )


class TestBaseMemoryAdapter:
    @pytest.mark.asyncio
    async def test_save_and_get(self):
        adapter = ConcreteAdapter()
        eid = await adapter.save(SaveRequest(content="hello"))
        assert eid is not None
        data = await adapter.get(eid)
        assert data["content"] == "hello"

    @pytest.mark.asyncio
    async def test_search(self):
        adapter = ConcreteAdapter()
        await adapter.save(SaveRequest(content="python pattern"))
        await adapter.save(SaveRequest(content="javascript tip"))
        results = await adapter.search("python")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_delete(self):
        adapter = ConcreteAdapter()
        eid = await adapter.save(SaveRequest(content="temp"))
        assert await adapter.delete(eid)
        assert await adapter.get(eid) is None

    @pytest.mark.asyncio
    async def test_update(self):
        adapter = ConcreteAdapter()
        eid = await adapter.save(SaveRequest(content="original"))
        assert await adapter.update(eid, {"content": "updated"})
        data = await adapter.get(eid)
        assert data["content"] == "updated"

    @pytest.mark.asyncio
    async def test_health_check(self):
        adapter = ConcreteAdapter()
        assert await adapter.health_check()


# =============================================================================
# PatternMerger Tests
# =============================================================================


class TestPatternMerger:
    @pytest.fixture
    def storage_dir(self, tmp_path):
        d = tmp_path / "skill_learning"
        d.mkdir()
        return d

    def _write_patterns(self, path: Path, patterns: list[dict]):
        with open(path, "w", encoding="utf-8") as f:
            for p in patterns:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")

    @pytest.mark.asyncio
    async def test_no_duplicates(self, storage_dir):
        self._write_patterns(
            storage_dir / "patterns.jsonl",
            [
                {
                    "pattern_id": "1",
                    "name": "a",
                    "content": "pattern A",
                    "confidence": 0.8,
                    "tags": ["x"],
                },
                {
                    "pattern_id": "2",
                    "name": "b",
                    "content": "pattern B",
                    "confidence": 0.9,
                    "tags": ["y"],
                },
            ],
        )
        merger = PatternMerger(storage_dir)
        result = await merger.merge_duplicates()
        assert result.duplicates_found == 0
        assert result.patterns_kept == 2

    @pytest.mark.asyncio
    async def test_merge_exact_duplicates(self, storage_dir):
        self._write_patterns(
            storage_dir / "patterns.jsonl",
            [
                {
                    "pattern_id": "1",
                    "name": "test",
                    "content": "hello world",
                    "confidence": 0.7,
                    "tags": ["a"],
                    "application_count": 5,
                    "created_at": "2026-01-01T00:00:00",
                },
                {
                    "pattern_id": "2",
                    "name": "test",
                    "content": "hello world",
                    "confidence": 0.9,
                    "tags": ["b"],
                    "application_count": 3,
                    "created_at": "2026-01-02T00:00:00",
                },
            ],
        )
        merger = PatternMerger(storage_dir)
        result = await merger.merge_duplicates(strategy=ConflictStrategy.KEEP_HIGHER_CONFIDENCE)
        assert result.duplicates_found == 1
        assert result.patterns_merged == 1
        assert result.patterns_kept == 1

    @pytest.mark.asyncio
    async def test_merge_preserves_tags_and_counts(self, storage_dir):
        self._write_patterns(
            storage_dir / "patterns.jsonl",
            [
                {
                    "pattern_id": "1",
                    "name": "x",
                    "content": "same content",
                    "confidence": 0.9,
                    "tags": ["a", "b"],
                    "application_count": 10,
                    "created_at": "2026-01-01T00:00:00",
                },
                {
                    "pattern_id": "2",
                    "name": "x",
                    "content": "same content",
                    "confidence": 0.5,
                    "tags": ["c"],
                    "application_count": 5,
                    "created_at": "2026-01-02T00:00:00",
                },
            ],
        )
        merger = PatternMerger(storage_dir)
        result = await merger.merge_duplicates()
        # After merge, the file should have 1 pattern with merged tags and counts
        patterns_file = storage_dir / "patterns.jsonl"
        with open(patterns_file) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 1
        merged = json.loads(lines[0])
        assert set(merged["tags"]) == {"a", "b", "c"}
        assert merged["application_count"] == 15

    @pytest.mark.asyncio
    async def test_dry_run_no_write(self, storage_dir):
        self._write_patterns(
            storage_dir / "patterns.jsonl",
            [
                {"pattern_id": "1", "content": "same", "confidence": 0.7, "tags": []},
                {"pattern_id": "2", "content": "same", "confidence": 0.9, "tags": []},
            ],
        )
        merger = PatternMerger(storage_dir)
        result = await merger.merge_duplicates(dry_run=True)
        assert result.duplicates_found == 1
        # File unchanged
        with open(storage_dir / "patterns.jsonl") as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 2

    @pytest.mark.asyncio
    async def test_find_duplicates(self, storage_dir):
        self._write_patterns(
            storage_dir / "patterns.jsonl",
            [
                {"pattern_id": "1", "content": "unique", "confidence": 0.7, "tags": []},
                {"pattern_id": "2", "content": "dup", "confidence": 0.8, "tags": []},
                {"pattern_id": "3", "content": "dup", "confidence": 0.9, "tags": []},
            ],
        )
        merger = PatternMerger(storage_dir)
        groups = await merger.find_duplicates()
        assert len(groups) == 1
        assert len(groups[0]) == 2

    @pytest.mark.asyncio
    async def test_empty_storage(self, storage_dir):
        merger = PatternMerger(storage_dir)
        result = await merger.merge_duplicates()
        assert result.duplicates_found == 0
        assert result.patterns_kept == 0
