"""Governance wiring — roadmap 260611 P2 (F8 versioning, F9 TTL enforcement).

F8: orchestrator-mediated mutations snapshot versions (ADR-V variant A,
wire-minimal): propagation handlers write UPDATE versions, rollback writes the
snapshot back to the store so readers see the old content.

F9: memory_ttl_cleanup enforces expiry on the backing stores (memory-ai DELETE,
vector-memory archive via expired_at) instead of only trimming its own ledger,
and answers honestly (store_actions / failed — same pattern as P1.1).

asyncio_mode=auto → async def + await directly (no asyncio.run).
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from src.memory.ai_memory.services.ttl_service import TTLPolicy, TTLService
from src.memory.ai_memory.services.versioning_service import ChangeType, VersioningService
from src.memory.orchestrator.memory_orchestrator import MemoryOrchestrator
from src.memory.orchestrator.unified_id import SourceServer

pytestmark = pytest.mark.unit


def _make_memory_ai_db(path, rows: list[tuple[str, str, float]]) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE important_messages ("
        "id TEXT PRIMARY KEY, content TEXT, importance REAL DEFAULT 0.5, "
        "category TEXT, tags TEXT, created_at TEXT, updated_at TEXT, metadata TEXT)"
    )
    conn.executemany(
        "INSERT INTO important_messages (id, content, importance) VALUES (?, ?, ?)", rows
    )
    conn.commit()
    conn.close()


def _row(db, mid: str) -> tuple[str, float] | None:
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT content, importance FROM important_messages WHERE id = ?", (mid,)
        ).fetchone()
        return (row[0], row[1]) if row else None
    finally:
        conn.close()


def _orch(tmp_path, with_versions: bool = False, with_ttl: bool = False) -> MemoryOrchestrator:
    orch = MemoryOrchestrator()
    if with_versions:
        orch._versioning_service = VersioningService(storage_path=tmp_path / "versions.jsonl")
    if with_ttl:
        orch._ttl_service = TTLService(storage_path=str(tmp_path / "ttl.jsonl"))
    return orch


# ---------------------------------------------------------------------------
# F8 — versioning wiring
# ---------------------------------------------------------------------------


async def test_propagation_handler_writes_update_version(tmp_path, monkeypatch):
    """memory-ai handler mutation → UPDATE version in the store (F8)."""
    db = tmp_path / "memory_ai.db"
    _make_memory_ai_db(db, [("m1", "hello", 0.50)])
    monkeypatch.setenv("MEMORY_AI_DB_PATH", str(db))

    orch = _orch(tmp_path, with_versions=True)
    handler = orch._build_propagation_handlers()[SourceServer.MEMORY_AI]
    assert await handler("episodic:memory-ai:m1", 0.2) is True

    versions = await orch._versioning_service.get_version_history("episodic:memory-ai:m1")
    assert len(versions) == 1
    assert versions[0].change_type is ChangeType.UPDATE
    assert versions[0].content["importance"] == pytest.approx(0.70)

    # Honest no-op (missing entity) does NOT version.
    assert await handler("episodic:memory-ai:nope", 0.2) is False
    versions = await orch._versioning_service.get_version_history("episodic:memory-ai:nope")
    assert versions == []


async def test_version_write_is_fail_soft(tmp_path):
    """A versioning failure must never fail the primary write."""

    class _Broken:
        async def create_version(self, **kw):
            raise OSError("disk full")

    orch = MemoryOrchestrator()
    orch._versioning_service = _Broken()
    # Must not raise.
    await orch._version_write("episodic:memory-ai:m1", {"x": 1}, ChangeType.UPDATE)


async def test_rollback_writes_back_to_memory_ai(tmp_path, monkeypatch):
    """D3 acceptance core: history → rollback → читатель видит старый контент."""
    db = tmp_path / "memory_ai.db"
    _make_memory_ai_db(db, [("m1", "original content", 0.50)])
    monkeypatch.setenv("MEMORY_AI_DB_PATH", str(db))

    orch = _orch(tmp_path, with_versions=True)
    eid = "episodic:memory-ai:m1"

    # v1 CREATE snapshot, then the entity mutates in the store.
    await orch._versioning_service.create_version(
        eid, {"content": "original content", "importance": 0.50}, ChangeType.CREATE
    )
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE important_messages SET content = 'mutated', importance = 0.9 WHERE id = 'm1'"
    )
    conn.commit()
    conn.close()
    await orch._versioning_service.create_version(
        eid, {"content": "mutated", "importance": 0.9}, ChangeType.UPDATE
    )

    resp = await orch.memory_version_rollback(eid, target_version=1)
    assert resp["success"] is True
    assert resp["store_writeback"]["applied"] is True
    assert sorted(resp["store_writeback"]["fields"]) == ["content", "importance"]

    # Reader sees the rolled-back content.
    assert _row(db, "m1") == ("original content", pytest.approx(0.50))

    # History: CREATE + UPDATE + ROLLBACK
    hist = await orch.memory_version_history(eid)
    assert hist["count"] == 3


async def test_rollback_create_snapshot_unwraps_metadata_importance(tmp_path, monkeypatch):
    """F16 (260611 §18 live re-run): route_and_save CREATE-snapshots keep
    importance under metadata — rollback to v1 must restore it, not only content."""
    db = tmp_path / "memory_ai.db"
    _make_memory_ai_db(db, [("m1", "original content", 0.40)])
    monkeypatch.setenv("MEMORY_AI_DB_PATH", str(db))

    orch = _orch(tmp_path, with_versions=True)
    eid = "episodic:memory-ai:m1"

    # v1 in route_and_save's shape: importance nested in metadata.
    await orch._versioning_service.create_version(
        eid,
        {
            "content": "original content",
            "metadata": {"importance": 0.40, "category": "test"},
            "target": "memory-ai",
        },
        ChangeType.CREATE,
    )
    # Propagation nudge mutates the store + writes the UPDATE snapshot.
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE important_messages SET importance = 0.4225 WHERE id = 'm1'")
    conn.commit()
    conn.close()
    await orch._versioning_service.create_version(eid, {"importance": 0.4225}, ChangeType.UPDATE)

    resp = await orch.memory_version_rollback(eid, target_version=1)
    assert resp["success"] is True
    assert sorted(resp["store_writeback"]["fields"]) == ["content", "importance"]
    assert _row(db, "m1") == ("original content", pytest.approx(0.40))


async def test_rollback_unsupported_source_is_honest(tmp_path):
    orch = _orch(tmp_path, with_versions=True)
    eid = "learning:skill-learning:p1"
    await orch._versioning_service.create_version(eid, {"content": "x"}, ChangeType.CREATE)
    resp = await orch.memory_version_rollback(eid, target_version=1)
    assert resp["success"] is True
    assert resp["store_writeback"]["applied"] is False
    assert resp["store_writeback"]["reason"].startswith("unsupported_source:")


# ---------------------------------------------------------------------------
# F9 — TTL enforcement
# ---------------------------------------------------------------------------


async def test_ttl_cleanup_deletes_memory_ai_row(tmp_path, monkeypatch):
    """D2 acceptance core: expired memory-ai entity disappears from the store."""
    db = tmp_path / "memory_ai.db"
    _make_memory_ai_db(db, [("m1", "ephemeral", 0.5), ("m2", "keeper", 0.5)])
    monkeypatch.setenv("MEMORY_AI_DB_PATH", str(db))

    orch = _orch(tmp_path, with_ttl=True)
    await orch._ttl_service.register(
        "episodic:memory-ai:m1", policy=TTLPolicy.CUSTOM, ttl_seconds=-1
    )

    resp = await orch.memory_ttl_cleanup()
    assert resp["success"] is True
    assert resp["removed_ledger"] == 1
    assert resp["store_actions"]["deleted"] == ["episodic:memory-ai:m1"]
    assert resp["failed"] == {}

    assert _row(db, "m1") is None
    assert _row(db, "m2") is not None  # untouched


async def test_ttl_cleanup_archives_vector_pattern(tmp_path, monkeypatch):
    """vector-memory entity is ARCHIVED (expired_at), not deleted — §22 semantics."""
    from src.memory.vector_memory import server as vm_server

    monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path / "cache"))

    set_calls: list[dict] = []

    class _FakeQdrant:
        def retrieve(self, collection_name, ids, with_payload=False):
            return [SimpleNamespace(id=ids[0], payload={})]

        def set_payload(self, collection_name, payload, points):
            set_calls.append({"payload": payload, "points": points})

    monkeypatch.setattr(vm_server, "_get_qdrant", lambda: _FakeQdrant())

    orch = _orch(tmp_path, with_ttl=True)
    await orch._ttl_service.register(
        "semantic:vector-memory:p1", policy=TTLPolicy.CUSTOM, ttl_seconds=-1
    )

    resp = await orch.memory_ttl_cleanup()
    assert resp["store_actions"]["archived"] == ["semantic:vector-memory:p1"]
    assert set_calls and "expired_at" in set_calls[0]["payload"]


async def test_ttl_cleanup_honest_skip_and_fail(tmp_path, monkeypatch):
    """Unparseable / unsupported / handler-raise — every outcome is visible."""
    from src.memory.vector_memory import server as vm_server

    def _boom():
        raise ConnectionError("qdrant down")

    monkeypatch.setattr(vm_server, "_get_qdrant", _boom)

    orch = _orch(tmp_path, with_ttl=True)
    for eid in (
        "not-a-unified-id",
        "learning:skill-learning:p1",
        "semantic:vector-memory:p2",
    ):
        await orch._ttl_service.register(eid, policy=TTLPolicy.CUSTOM, ttl_seconds=-1)

    resp = await orch.memory_ttl_cleanup()
    assert resp["success"] is False  # the vector failure is not swallowed
    assert resp["store_actions"]["skipped"]["not-a-unified-id"] == "unparseable_id"
    assert resp["store_actions"]["skipped"]["learning:skill-learning:p1"].startswith(
        "unsupported_source:"
    )
    assert resp["failed"] == {"semantic:vector-memory:p2": "ConnectionError"}
