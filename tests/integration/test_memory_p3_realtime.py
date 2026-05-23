"""
Integration tests for Memory System P3 — Realtime components.

Tests:
- EventBus: publish/subscribe, wildcards, backpressure, lifecycle (10 tests)
- EventStore: append, query, flush, replay, lifecycle (8 tests)
- ConflictResolver: all 4 strategies, field/dict merge (10 tests)

Total: 28 tests.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.memory.infrastructure.conflict_resolver import (
    ConflictResolver,
    ConflictStrategy,
)
from src.memory.infrastructure.event_bus import (
    Event,
    EventBus,
    EventBusConfig,
)
from src.memory.infrastructure.event_store import EventStore, EventStoreConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def bus():
    """Provide a started EventBus with small queue for testing."""
    eb = EventBus(EventBusConfig(max_queue_size=10, max_subscribers=5, enable_logging=False))
    await eb.start()
    yield eb
    await eb.stop()


@pytest.fixture
async def store(tmp_path):
    """Provide a started EventStore with temp paths."""
    es = EventStore(
        EventStoreConfig(
            hot_buffer_path=str(tmp_path / "events.jsonl"),
            cold_db_path=str(tmp_path / "events.db"),
            auto_flush_threshold=500,
            flush_interval=3600.0,
        )
    )
    await es.start()
    yield es
    await es.stop()


@pytest.fixture
def resolver():
    """ConflictResolver with source priority ordering."""
    return ConflictResolver(
        default_strategy=ConflictStrategy.LAST_WRITE_WINS,
        source_priorities=["memory-ai", "vector-memory", "skill-learning"],
    )


def _make_event(event_type: str = "test.event", **data) -> Event:
    """Helper to create Event instances for tests."""
    return Event(
        event_id=f"test-{uuid4().hex[:12]}",
        event_type=event_type,
        data=data,
        timestamp=datetime.now(tz=UTC),
        source="test",
    )


# ---------------------------------------------------------------------------
# TestEventBus — 10 tests
# ---------------------------------------------------------------------------


class TestEventBus:
    @pytest.mark.asyncio
    async def test_publish_subscribe(self, bus):
        sub = await bus.subscribe("memory.save")
        await bus.publish("memory.save", {"key": "val"})
        await asyncio.sleep(0.05)
        event = sub.queue.get_nowait()
        assert event.event_type == "memory.save"
        assert event.data == {"key": "val"}

    @pytest.mark.asyncio
    async def test_wildcard_single_level(self, bus):
        sub = await bus.subscribe("memory.*")
        await bus.publish("memory.save", {"a": 1})
        await bus.publish("memory.save.deep", {"b": 2})
        await asyncio.sleep(0.05)
        assert sub.queue.qsize() == 1
        event = sub.queue.get_nowait()
        assert event.data == {"a": 1}

    @pytest.mark.asyncio
    async def test_wildcard_multi_level(self, bus):
        sub = await bus.subscribe("memory.**")
        await bus.publish("memory.save.deep.nested", {"x": 1})
        await bus.publish("memory.save", {"y": 2})
        await asyncio.sleep(0.05)
        assert sub.queue.qsize() == 2

    @pytest.mark.asyncio
    async def test_exact_match(self, bus):
        sub = await bus.subscribe("memory.save")
        await bus.publish("memory.save", {"ok": True})
        await bus.publish("memory.delete", {"ok": False})
        await asyncio.sleep(0.05)
        assert sub.queue.qsize() == 1
        assert sub.queue.get_nowait().data == {"ok": True}

    @pytest.mark.asyncio
    async def test_unsubscribe(self, bus):
        sub = await bus.subscribe("memory.del")
        await bus.unsubscribe(sub.subscription_id)
        await bus.publish("memory.del", {"gone": True})
        await asyncio.sleep(0.05)
        assert sub.queue.empty()

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, bus):
        sub1 = await bus.subscribe("memory.dup")
        sub2 = await bus.subscribe("memory.dup")
        await bus.publish("memory.dup", {"v": 42})
        await asyncio.sleep(0.05)
        assert sub1.queue.qsize() == 1
        assert sub2.queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_backpressure(self):
        eb = EventBus(EventBusConfig(max_queue_size=2, max_subscribers=5, enable_logging=False))
        await eb.start()
        sub = await eb.subscribe("bp.test")
        for i in range(5):
            await eb.publish("bp.test", {"i": i})
        await asyncio.sleep(0.1)
        stats = eb.get_stats()
        assert stats.dropped_count > 0
        assert sub.queue.qsize() == 2
        await eb.stop()

    @pytest.mark.asyncio
    async def test_get_stats(self, bus):
        await bus.subscribe("stats.test")
        await bus.publish("stats.test", {})
        await asyncio.sleep(0.05)
        stats = bus.get_stats()
        assert stats.published_count >= 1
        assert stats.subscriber_count >= 1

    @pytest.mark.asyncio
    async def test_start_stop(self):
        eb = EventBus(EventBusConfig(enable_logging=False))
        await eb.start()
        await eb.stop()
        await eb.start()
        await eb.stop()

    @pytest.mark.asyncio
    async def test_max_subscribers(self):
        eb = EventBus(EventBusConfig(max_subscribers=2, enable_logging=False))
        await eb.start()
        await eb.subscribe("lim.a")
        await eb.subscribe("lim.b")
        with pytest.raises(RuntimeError, match="Maximum subscriber limit"):
            await eb.subscribe("lim.c")
        await eb.stop()


# ---------------------------------------------------------------------------
# TestEventStore — 8 tests
# ---------------------------------------------------------------------------


class TestEventStore:
    @pytest.mark.asyncio
    async def test_append_and_query(self, store):
        await store.append(_make_event("a.b", i=1))
        await store.append(_make_event("c.d", i=2))
        results = await store.query()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_by_type(self, store):
        await store.append(_make_event("alpha", x=1))
        await store.append(_make_event("beta", x=2))
        await store.append(_make_event("alpha", x=3))
        results = await store.query(event_type="alpha")
        assert len(results) == 2
        assert all(r.event_type == "alpha" for r in results)

    @pytest.mark.asyncio
    async def test_query_by_time_range(self, store):
        now = datetime.now(tz=UTC)
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)
        e1 = Event(event_id="t1", event_type="t", data={"v": 1}, timestamp=past, source="test")
        e2 = Event(event_id="t2", event_type="t", data={"v": 2}, timestamp=now, source="test")
        e3 = Event(event_id="t3", event_type="t", data={"v": 3}, timestamp=future, source="test")
        await store.append(e1)
        await store.append(e2)
        await store.append(e3)
        results = await store.query(start=past, end=now)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_flush(self, store):
        for i in range(3):
            await store.append(_make_event("flush", i=i))
        await store.flush()
        stats = await store.get_stats()
        assert stats["hot_buffer_size"] == 0
        assert stats["cold_storage_size"] == 3
        results = await store.query()
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_auto_flush(self, tmp_path):
        es = EventStore(
            EventStoreConfig(
                hot_buffer_path=str(tmp_path / "af.jsonl"),
                cold_db_path=str(tmp_path / "af.db"),
                auto_flush_threshold=3,
                flush_interval=3600.0,
            )
        )
        await es.start()
        for i in range(4):
            await es.append(_make_event("auto", i=i))
        stats = await es.get_stats()
        assert stats["cold_storage_size"] >= 3
        await es.stop()

    @pytest.mark.asyncio
    async def test_replay(self, store):
        await store.append(_make_event("r", i=1))
        await store.append(_make_event("r", i=2))
        replayed = []
        count = await store.replay(event_type="r", callback=lambda e: replayed.append(e))
        assert count == 2
        assert len(replayed) == 2

    @pytest.mark.asyncio
    async def test_get_stats(self, store):
        await store.append(_make_event("s", x=1))
        await store.append(_make_event("s", x=2))
        stats = await store.get_stats()
        assert stats["total_events"] == 2
        assert stats["hot_buffer_size"] == 2

    @pytest.mark.asyncio
    async def test_start_stop(self, tmp_path):
        es = EventStore(
            EventStoreConfig(
                hot_buffer_path=str(tmp_path / "lc.jsonl"),
                cold_db_path=str(tmp_path / "lc.db"),
            )
        )
        await es.start()
        await es.stop()


# ---------------------------------------------------------------------------
# TestConflictResolver — 10 tests
# ---------------------------------------------------------------------------


class TestConflictResolver:
    def test_last_write_wins_incoming(self, resolver):
        now = datetime.now(tz=UTC)
        result = resolver.resolve(
            current={"_entity_id": "e1", "_timestamp": now, "_source": "a", "val": 1},
            incoming={
                "_entity_id": "e1",
                "_timestamp": now + timedelta(seconds=10),
                "_source": "b",
                "val": 2,
            },
            strategy=ConflictStrategy.LAST_WRITE_WINS,
        )
        assert result.resolved is True
        assert result.resolved_value["val"] == 2

    def test_last_write_wins_current(self, resolver):
        now = datetime.now(tz=UTC)
        result = resolver.resolve(
            current={
                "_entity_id": "e1",
                "_timestamp": now + timedelta(seconds=10),
                "_source": "a",
                "val": 1,
            },
            incoming={"_entity_id": "e1", "_timestamp": now, "_source": "b", "val": 2},
            strategy=ConflictStrategy.LAST_WRITE_WINS,
        )
        assert result.resolved is True
        assert result.resolved_value["val"] == 1

    def test_source_priority(self, resolver):
        now = datetime.now(tz=UTC)
        result = resolver.resolve(
            current={"_entity_id": "e1", "_timestamp": now, "_source": "skill-learning", "val": 1},
            incoming={"_entity_id": "e1", "_timestamp": now, "_source": "memory-ai", "val": 2},
            strategy=ConflictStrategy.SOURCE_PRIORITY,
        )
        assert result.resolved is True
        assert result.resolved_value["val"] == 2

    def test_source_priority_unknown(self, resolver):
        now = datetime.now(tz=UTC)
        result = resolver.resolve(
            current={"_entity_id": "e1", "_timestamp": now, "_source": "memory-ai", "val": 1},
            incoming={"_entity_id": "e1", "_timestamp": now, "_source": "unknown-src", "val": 2},
            strategy=ConflictStrategy.SOURCE_PRIORITY,
        )
        assert result.resolved is True
        assert result.resolved_value["val"] == 1

    def test_merge_fields_no_conflict(self, resolver):
        now = datetime.now(tz=UTC)
        result = resolver.resolve(
            current={"_entity_id": "e1", "_timestamp": now, "_source": "a", "alpha": 1},
            incoming={"_entity_id": "e1", "_timestamp": now, "_source": "b", "beta": 2},
            strategy=ConflictStrategy.MERGE_FIELDS,
        )
        assert result.resolved is True
        assert result.resolved_value["alpha"] == 1
        assert result.resolved_value["beta"] == 2
        assert len(result.conflicts) == 0

    def test_merge_fields_with_conflict(self, resolver):
        now = datetime.now(tz=UTC)
        result = resolver.resolve(
            current={"_entity_id": "e1", "_timestamp": now, "_source": "a", "shared": 1},
            incoming={"_entity_id": "e1", "_timestamp": now, "_source": "b", "shared": 2},
            strategy=ConflictStrategy.MERGE_FIELDS,
        )
        assert result.resolved is False
        assert len(result.conflicts) == 1
        assert result.conflicts[0].field_name == "shared"

    def test_manual(self, resolver):
        now = datetime.now(tz=UTC)
        result = resolver.resolve(
            current={"_entity_id": "e1", "_timestamp": now, "_source": "a", "x": 1, "y": 2},
            incoming={"_entity_id": "e1", "_timestamp": now, "_source": "b", "x": 10, "y": 2},
            strategy=ConflictStrategy.MANUAL,
        )
        assert result.resolved is False
        assert result.resolved_value is None
        assert len(result.conflicts) == 1
        assert result.conflicts[0].field_name == "x"

    def test_resolve_field_equal(self, resolver):
        now = datetime.now(tz=UTC)
        val, was_conflict = resolver.resolve_field("status", "active", "active", now, now, "a", "b")
        assert val == "active"
        assert was_conflict is False

    def test_resolve_field_different(self, resolver):
        now = datetime.now(tz=UTC)
        val, was_conflict = resolver.resolve_field(
            "status",
            "active",
            "inactive",
            now,
            now + timedelta(seconds=1),
            "a",
            "b",
        )
        assert was_conflict is True
        assert val == "inactive"

    def test_merge_dicts(self, resolver):
        merged, conflicts = resolver.merge_dicts(
            current={"_entity_id": "e1", "a": 1, "b": 2},
            incoming={"_entity_id": "e1", "b": 99, "c": 3},
        )
        assert merged["a"] == 1
        assert merged["b"] == 99
        assert merged["c"] == 3
        assert len(conflicts) == 1
        assert conflicts[0].field_name == "b"
