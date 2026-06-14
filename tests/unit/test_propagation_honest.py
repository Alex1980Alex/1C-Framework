"""Honest propagation semantics — roadmap 260609 P2.3.

Pins the fix for the "simulate success" lie: ``PropagationEngine`` must only
report an entity in ``entities_updated`` when a registered handler actually
mutated it. With no handler (or a handler that reports no change) nothing is
counted — callers never see phantom updates.

Also exercises the real ``memory-ai`` update handler wired by
``MemoryOrchestrator._build_propagation_handlers`` against a temp SQLite DB
(``MEMORY_AI_DB_PATH`` override), so it never touches the production store.

asyncio_mode=auto → write ``async def`` + ``await`` directly (no asyncio.run).
"""

from __future__ import annotations

import sqlite3

import pytest

from src.memory.orchestrator.link_registry import LinkRegistry, LinkType
from src.memory.orchestrator.memory_orchestrator import MemoryOrchestrator
from src.memory.orchestrator.propagation_engine import (
    PropagationConfig,
    PropagationEngine,
)
from src.memory.orchestrator.unified_id import SourceServer

pytestmark = pytest.mark.unit


def _linked_registry(tmp_path):
    reg = LinkRegistry(db_path=str(tmp_path / "links.db"))
    reg.create_link(
        "semantic:vector-memory:a",
        "semantic:vector-memory:b",
        LinkType.SUPPORTS,
        strength=0.9,
    )
    return reg


def _sync_engine(reg, **handlers):
    return PropagationEngine(
        reg,
        PropagationConfig(enable_background_processing=False, enable_time_decay=False),
        update_handlers=handlers.get("update_handlers"),
    )


async def test_no_handler_yields_no_phantom_updates(tmp_path):
    """The bug: pre-fix this returned entities_updated with a phantom 'b'."""
    engine = _sync_engine(_linked_registry(tmp_path))
    result = await engine.propagate("semantic:vector-memory:a", 0.1)
    assert result.entities_updated == []


async def test_handler_returning_false_is_not_counted(tmp_path):
    calls: list[str] = []

    async def _refuse(entity_id: str, delta: float) -> bool:
        calls.append(entity_id)
        return False

    engine = _sync_engine(
        _linked_registry(tmp_path),
        update_handlers={SourceServer.VECTOR_MEMORY: _refuse},
    )
    result = await engine.propagate("semantic:vector-memory:a", 0.1)
    # Handler ran (so the engine *tried*) but reported no mutation → not counted.
    assert calls == ["semantic:vector-memory:b"]
    assert result.entities_updated == []


async def test_handler_returning_true_is_counted(tmp_path):
    seen: list[tuple[str, float]] = []

    async def _ok(entity_id: str, delta: float) -> bool:
        seen.append((entity_id, delta))
        return True

    engine = _sync_engine(
        _linked_registry(tmp_path),
        update_handlers={SourceServer.VECTOR_MEMORY: _ok},
    )
    result = await engine.propagate("semantic:vector-memory:a", 0.1)
    assert result.entities_updated == ["semantic:vector-memory:b"]
    assert seen and seen[0][0] == "semantic:vector-memory:b"
    assert seen[0][1] > 0  # positive delta propagated (boost direction)


async def test_handler_raise_lands_in_failed_entities(tmp_path):
    """roadmap 260611 P1.1 (F10): a handler exception is not an honest no-op —
    the entity must surface in failed_entities with the exception type."""

    async def _boom(entity_id: str, delta: float) -> bool:
        raise ConnectionError("qdrant down")

    engine = _sync_engine(
        _linked_registry(tmp_path),
        update_handlers={SourceServer.VECTOR_MEMORY: _boom},
    )
    result = await engine.propagate("semantic:vector-memory:a", 0.1)
    assert result.entities_updated == []
    assert result.failed_entities == {"semantic:vector-memory:b": "ConnectionError"}
    assert result.to_dict()["failed_entities"] == result.failed_entities
    assert engine.get_stats()["entities_failed"] == 1


async def test_mixed_success_and_failure(tmp_path):
    """vector arm fails, memory-ai arm applies — both visible, neither lost."""
    reg = LinkRegistry(db_path=str(tmp_path / "links.db"))
    reg.create_link(
        "semantic:vector-memory:a",
        "semantic:vector-memory:b",
        LinkType.SUPPORTS,
        strength=0.9,
    )
    reg.create_link(
        "semantic:vector-memory:a",
        "episodic:memory-ai:m1",
        LinkType.SUPPORTS,
        strength=0.9,
    )

    async def _boom(entity_id: str, delta: float) -> bool:
        raise ConnectionError("qdrant down")

    async def _ok(entity_id: str, delta: float) -> bool:
        return True

    engine = _sync_engine(
        reg,
        update_handlers={
            SourceServer.VECTOR_MEMORY: _boom,
            SourceServer.MEMORY_AI: _ok,
        },
    )
    result = await engine.propagate("semantic:vector-memory:a", 0.1)
    assert result.entities_updated == ["episodic:memory-ai:m1"]
    assert result.failed_entities == {"semantic:vector-memory:b": "ConnectionError"}


async def test_named_breaker_opens_and_fails_fast(tmp_path):
    """roadmap 260611 P1.2 (F10): handler failures trip the named per-source
    breaker; once OPEN, updates fail fast with failed:circuit_open and the
    handler is no longer invoked. Reset returns it to CLOSED."""
    from src.memory.infrastructure.circuit_breaker import (
        CircuitBreakerRegistry,
        CircuitState,
    )

    calls: list[str] = []

    async def _boom(entity_id: str, delta: float) -> bool:
        calls.append(entity_id)
        raise ConnectionError("qdrant down")

    registry = CircuitBreakerRegistry()
    reg = _linked_registry(tmp_path)
    engine = PropagationEngine(
        reg,
        PropagationConfig(
            enable_background_processing=False,
            enable_event_deduplication=False,
            enable_time_decay=False,
            circuit_breaker_threshold=3,
            # Large reset_timeout → no flaky HALF_OPEN transition mid-test.
            circuit_breaker_timeout=3600.0,
        ),
        update_handlers={SourceServer.VECTOR_MEMORY: _boom},
        breaker_registry=registry,
    )

    # 3 failing propagations trip the breaker (threshold=3, 1 handler call each).
    for _ in range(3):
        result = await engine.propagate("semantic:vector-memory:a", 0.1)
        assert result.failed_entities["semantic:vector-memory:b"] == "ConnectionError"

    breaker = registry.get("propagation:vector-memory")
    assert breaker is not None
    assert breaker.state == CircuitState.OPEN

    # OPEN → fail-fast, handler NOT called again.
    calls_before = len(calls)
    result = await engine.propagate("semantic:vector-memory:a", 0.1)
    assert result.failed_entities == {"semantic:vector-memory:b": "circuit_open"}
    assert len(calls) == calls_before

    # Reset → CLOSED → handler invoked again.
    breaker.reset()
    assert breaker.state == CircuitState.CLOSED
    result = await engine.propagate("semantic:vector-memory:a", 0.1)
    assert len(calls) == calls_before + 1


def _make_memory_ai_db(path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE important_messages ("
        "id TEXT PRIMARY KEY, content TEXT, importance REAL DEFAULT 0.5, "
        "category TEXT, tags TEXT, created_at TEXT, updated_at TEXT, metadata TEXT)"
    )
    conn.execute(
        "INSERT INTO important_messages (id, content, importance) VALUES (?, ?, ?)",
        ("m1", "hello", 0.50),
    )
    conn.commit()
    conn.close()


async def test_memory_ai_handler_mutates_importance(tmp_path, monkeypatch):
    db = tmp_path / "memory_ai.db"
    _make_memory_ai_db(db)
    monkeypatch.setenv("MEMORY_AI_DB_PATH", str(db))

    handlers = MemoryOrchestrator()._build_propagation_handlers()
    ai_handler = handlers[SourceServer.MEMORY_AI]

    # Existing message → importance nudged by delta, returns True.
    assert await ai_handler("episodic:memory-ai:m1", 0.2) is True
    conn = sqlite3.connect(str(db))
    imp = conn.execute("SELECT importance FROM important_messages WHERE id = 'm1'").fetchone()[0]
    conn.close()
    assert imp == pytest.approx(0.70, abs=1e-6)

    # Missing message → honest False, no fabrication.
    assert await ai_handler("episodic:memory-ai:does-not-exist", 0.2) is False


async def test_memory_ai_handler_clamps_importance(tmp_path, monkeypatch):
    db = tmp_path / "memory_ai.db"
    _make_memory_ai_db(db)
    monkeypatch.setenv("MEMORY_AI_DB_PATH", str(db))

    ai_handler = MemoryOrchestrator()._build_propagation_handlers()[SourceServer.MEMORY_AI]
    # Large positive delta clamps at 1.0.
    assert await ai_handler("episodic:memory-ai:m1", 5.0) is True
    conn = sqlite3.connect(str(db))
    imp = conn.execute("SELECT importance FROM important_messages WHERE id = 'm1'").fetchone()[0]
    conn.close()
    assert imp == pytest.approx(1.0, abs=1e-6)


async def test_orchestrator_propagate_is_sync_and_repeatable(tmp_path, monkeypatch):
    """Production MCP path returns the real result, twice in a row.

    Pins the lazy-init config: with the engine defaults the first call would
    come back ``reason="queued_for_background_processing"`` with
    ``entities_updated=[]`` (hiding the honest result behind the queue), and
    event dedup would silently skip the second call for the same entity.
    """
    calls: list[str] = []

    async def _ok(entity_id: str, delta: float) -> bool:
        calls.append(entity_id)
        return True

    orch = MemoryOrchestrator()
    orch._link_registry = _linked_registry(tmp_path)
    monkeypatch.setattr(
        orch,
        "_build_propagation_handlers",
        lambda: {SourceServer.VECTOR_MEMORY: _ok},
    )

    for _ in range(2):
        resp = await orch.propagate_update("semantic:vector-memory:a", delta=0.1)
        assert resp["success"] is True
        result = resp["result"]
        assert result["reason"] != "queued_for_background_processing"
        assert result["entities_updated"] == ["semantic:vector-memory:b"]

    # Both invocations reached the handler — no duplicate_event swallowing.
    assert calls == ["semantic:vector-memory:b"] * 2

    await orch._propagation_engine.stop()


async def test_vector_handler_bumps_epoch(tmp_path, monkeypatch):
    """§24 invariant: the vector-memory propagation handler is a confidence
    writer, so a successful mutation must bump the surfacing-cache epoch."""
    from types import SimpleNamespace

    from src.memory.vector_memory import epoch
    from src.memory.vector_memory import server as vm_server

    monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path / "cache"))
    assert epoch.read() == 0.0

    class _FakeQdrant:
        def retrieve(self, collection_name, ids, with_payload):
            return [SimpleNamespace(payload={"succ": 1.0, "fail": 0.0, "confidence": 0.7})]

        def set_payload(self, collection_name, payload, points):
            pass

    monkeypatch.setattr(vm_server, "_get_qdrant", lambda: _FakeQdrant())

    handler = MemoryOrchestrator()._build_propagation_handlers()[SourceServer.VECTOR_MEMORY]
    assert await handler("semantic:vector-memory:p1", 1.0) is True
    assert epoch.read() > 0.0
