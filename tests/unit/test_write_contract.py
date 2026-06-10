"""Unit tests for the §26 write-contract in direct writers (roadmap 260609 P1.3)
and honest partial-failure reporting in route_and_save (P1.4).

Covers:
  - shared ``content_hash.point_id`` determinism + namespace (harvester compat)
  - ``_pattern_to_payload`` stamps ``content_hash``
  - ``save_pattern`` dedup: re-saving identical content → action=dup, no new point
  - ``save_important_message`` content-equality dedup
  - ``capture_pattern`` dedup across pending+saved silos
  - ``route_and_save`` reports failed_targets / success=False / saved_partial

All writers honor CLAUDE_CACHE_DIR / tmp paths via the conftest sink isolation,
so nothing here touches a production store or sink.
"""

from __future__ import annotations

import json
import types
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# point_id — deterministic, harvester-namespace-compatible
# ---------------------------------------------------------------------------
def test_point_id_deterministic_and_namespace():
    from src.memory.orchestrator.content_hash import hash_content, point_id

    ch = hash_content("some pattern content")
    pid1 = point_id(ch)
    pid2 = point_id(ch)
    assert pid1 == pid2  # stable across calls
    # Must use the harvester namespace so manual + harvested writes collide.
    expected = str(uuid.uuid5(uuid.UUID("a1b2c3d4-1111-2222-3333-444455556666"), ch))
    assert pid1 == expected
    # Different content → different id.
    assert point_id(hash_content("other content")) != pid1


# ---------------------------------------------------------------------------
# save_pattern — content_hash payload + dedup
# ---------------------------------------------------------------------------
class _FakePoint:
    def __init__(self, pid, payload):
        self.id = pid
        self.payload = payload


class _FakeQdrant:
    """Minimal stand-in: deterministic-id store with retrieve/upsert."""

    def __init__(self):
        self.store: dict = {}

    def retrieve(self, collection_name, ids):
        return [self.store[i] for i in ids if i in self.store]

    def upsert(self, collection_name, points):
        for p in points:
            self.store[p.id] = _FakePoint(p.id, p.payload)


def test_pattern_to_payload_has_content_hash():
    from src.memory.orchestrator.content_hash import hash_content
    from src.memory.vector_memory.models import LearnedPattern, PatternType
    from src.memory.vector_memory.server import _pattern_to_payload

    p = LearnedPattern(
        pattern_id="x",
        pattern_type=PatternType("code-convention"),
        name="n",
        description="",
        content="hash me please",
    )
    payload = _pattern_to_payload(p)
    assert payload["content_hash"] == hash_content("hash me please")


async def test_save_pattern_dedups_identical_content(monkeypatch):
    pytest.importorskip("qdrant_client")
    import src.memory.vector_memory.server as vm

    fake = _FakeQdrant()
    monkeypatch.setattr(vm, "_get_qdrant", lambda: fake)

    async def _fake_embed(text):
        return [0.1] * 8

    monkeypatch.setattr(vm, "_get_embedding", _fake_embed)

    args = {
        "pattern_type": "code-convention",
        "name": "dedup target",
        "content": "deterministic dedup content ABCXYZ",
    }

    r1 = json.loads((await vm.handle_save_pattern(args))[0].text)
    assert r1["action"] == "saved"
    assert len(fake.store) == 1
    pid = r1["pattern_id"]
    assert fake.store[pid].payload["content_hash"] == r1["content_hash"]

    # Second save of identical content → dup, no new point, same id.
    r2 = json.loads((await vm.handle_save_pattern(args))[0].text)
    assert r2["action"] == "dup"
    assert r2["pattern_id"] == pid
    assert len(fake.store) == 1


# ---------------------------------------------------------------------------
# save_important_message — content-equality dedup
# ---------------------------------------------------------------------------
async def test_save_important_message_dedups(monkeypatch, tmp_path):
    import src.memory.ai_memory.server as ai

    db = tmp_path / "mem.db"
    monkeypatch.setattr(ai, "DB_PATH", db)
    ai.ensure_db()

    msg = {"content": "an important fact worth remembering"}
    r1 = json.loads((await ai.save_important_message(msg))[0].text)
    assert r1["action"] == "saved"
    r2 = json.loads((await ai.save_important_message(msg))[0].text)
    assert r2["action"] == "dup"
    assert r2["id"] == r1["id"]


# ---------------------------------------------------------------------------
# capture_pattern — dedup across pending+saved
# ---------------------------------------------------------------------------
async def test_capture_pattern_dedups(monkeypatch, tmp_path):
    import src.memory.skill_learning.server as sl

    monkeypatch.setattr(sl, "PENDING_FILE", tmp_path / "pending.jsonl")
    monkeypatch.setattr(sl, "SAVED_FILE", tmp_path / "saved.jsonl")

    args = {"pattern_type": "workflow-pattern", "name": "p", "content": "capture dedup content"}
    r1 = json.loads((await sl.handle_capture_pattern(args))[0].text)
    assert r1["status"] == "pending"
    r2 = json.loads((await sl.handle_capture_pattern(args))[0].text)
    assert r2["action"] == "dup"


# ---------------------------------------------------------------------------
# route_and_save — honest partial-failure reporting (P1.4)
# ---------------------------------------------------------------------------
class _Decision:
    def __init__(self, targets):
        self.targets = targets
        self.method = "test"
        self.confidences = {}

    def to_dict(self):
        return {"targets": self.targets, "method": self.method}


def _make_orchestrator(targets):
    from src.memory.orchestrator.memory_orchestrator import MemoryOrchestrator

    orch = MemoryOrchestrator.__new__(MemoryOrchestrator)
    orch._track = lambda *a, **k: None
    router = MagicMock()
    router.route = AsyncMock(return_value=_Decision(targets))
    orch._router = router
    orch.config = types.SimpleNamespace(enable_link_creation=False)
    orch._link_registry = MagicMock()

    async def _noop_async(*a, **k):
        return None

    orch._emit_event = _noop_async
    orch._audit = _noop_async
    return orch


async def test_route_and_save_reports_partial_failure():
    orch = _make_orchestrator(["memory-ai", "vector-memory"])

    async def _fake_save(target, content, metadata):
        return None if target == "vector-memory" else f"id-{target}"

    orch._save_to_target = _fake_save

    result = await orch.route_and_save("partial save content", {})
    assert result["success"] is False
    assert result["saved_partial"] is True
    assert result["failed_targets"] == ["vector-memory"]
    assert len(result["saved_entities"]) == 1


async def test_route_and_save_full_success():
    orch = _make_orchestrator(["memory-ai", "skill-learning"])

    async def _fake_save(target, content, metadata):
        return f"id-{target}"

    orch._save_to_target = _fake_save

    result = await orch.route_and_save("all good content", {})
    assert result["success"] is True
    assert result["saved_partial"] is False
    assert result["failed_targets"] == []
    assert len(result["saved_entities"]) == 2


async def test_route_and_save_total_failure():
    orch = _make_orchestrator(["memory-ai", "vector-memory"])

    async def _fake_save(target, content, metadata):
        return None

    orch._save_to_target = _fake_save

    result = await orch.route_and_save("nothing saves", {})
    assert result["success"] is False
    assert result["saved_partial"] is False  # nothing saved → not "partial"
    assert set(result["failed_targets"]) == {"memory-ai", "vector-memory"}
