"""§27 cascade — apply_pattern → confidence propagation to linked neighbours.

Closes the §22 P3 deferred "neighbour-aware link_registry gate": apply_pattern now
nudges directly-linked neighbour patterns' Beta succ/fail (depth-1, same-store,
fail-soft, bounded). These tests prove the nudge math, the empty-graph no-op, and
the opt-out gate — Qdrant-independent (fake client + temp LinkRegistry).
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


class _FakePoint:
    def __init__(self, payload: dict) -> None:
        self.payload = payload


class _FakeClient:
    """Minimal Qdrant stand-in: dict-backed retrieve + set_payload recorder."""

    def __init__(self, points: dict[str, dict]) -> None:
        self.points = points
        self.set_calls: list[tuple[str, dict]] = []

    def retrieve(self, collection_name, ids, with_payload=True):
        return [_FakePoint(self.points[i]) for i in ids if i in self.points]

    def set_payload(self, collection_name, payload, points):
        self.set_calls.append((points[0], payload))
        self.points[points[0]].update(payload)


def _registry_factory(tmp_db: Path, monkeypatch):
    """Patch the module-level LinkRegistry so the helper's `LinkRegistry()` uses tmp db."""
    import memory.orchestrator.link_registry as lr

    real = lr.LinkRegistry
    monkeypatch.setattr(lr, "LinkRegistry", lambda: real(db_path=str(tmp_db)))
    return real, lr.LinkType


def _link(reg, src, tgt, link_type, strength=0.8):
    reg.create_link(source_id=src, target_id=tgt, link_type=link_type, strength=strength)


class TestApplyCascade:
    def test_nudges_linked_neighbour_on_success(self, tmp_path, monkeypatch):
        from memory.vector_memory.server import _cascade_confidence

        tmp_db = tmp_path / "link_registry.db"
        real_cls, LinkType = _registry_factory(tmp_db, monkeypatch)
        reg = real_cls(db_path=str(tmp_db))
        _link(
            reg,
            "semantic:vector-memory:A",
            "semantic:vector-memory:B",
            LinkType.SUPPORTS,
            strength=0.8,
        )

        client = _FakeClient(
            {"B": {"confidence": 0.70, "succ": 0.0, "fail": 0.0, "application_count": 0}}
        )
        stats = _cascade_confidence(client, "A", success=True, now=datetime.now())

        assert stats["entities_updated"] == 1
        assert client.set_calls and client.set_calls[0][0] == "B"
        new = client.points["B"]
        # delta = 1.0 * strength(0.8) * 0.5(dist) * ~1.0(time) = 0.4 → succ≈0.4
        assert new["succ"] == pytest.approx(0.4, abs=0.02)
        assert new["confidence"] > 0.70  # success raised neighbour confidence

    def test_fail_nudges_fail_count_down(self, tmp_path, monkeypatch):
        from memory.vector_memory.server import _cascade_confidence

        tmp_db = tmp_path / "link_registry.db"
        real_cls, LinkType = _registry_factory(tmp_db, monkeypatch)
        _link(
            real_cls(db_path=str(tmp_db)),
            "semantic:vector-memory:A",
            "semantic:vector-memory:B",
            LinkType.EXTENDS,
            strength=1.0,
        )

        client = _FakeClient(
            {"B": {"confidence": 0.70, "succ": 0.0, "fail": 0.0, "application_count": 0}}
        )
        stats = _cascade_confidence(client, "A", success=False, now=datetime.now())

        assert stats["entities_updated"] == 1
        assert client.points["B"]["fail"] == pytest.approx(0.5, abs=0.02)  # 1.0*0.5*1.0
        assert client.points["B"]["confidence"] < 0.70  # failure lowered it

    def test_no_links_is_noop(self, tmp_path, monkeypatch):
        from memory.vector_memory.server import _cascade_confidence

        tmp_db = tmp_path / "link_registry.db"
        real_cls, _ = _registry_factory(tmp_db, monkeypatch)
        real_cls(db_path=str(tmp_db))  # create empty registry

        client = _FakeClient({"B": {"confidence": 0.70, "succ": 0.0, "fail": 0.0}})
        stats = _cascade_confidence(client, "A", success=True, now=datetime.now())
        assert stats["entities_updated"] == 0
        assert client.set_calls == []

    def test_neighbour_not_a_pattern_is_prevented(self, tmp_path, monkeypatch):
        from memory.vector_memory.server import _cascade_confidence

        tmp_db = tmp_path / "link_registry.db"
        real_cls, LinkType = _registry_factory(tmp_db, monkeypatch)
        _link(
            real_cls(db_path=str(tmp_db)),
            "semantic:vector-memory:A",
            "semantic:vector-memory:C",
            LinkType.SUPPORTS,
        )

        client = _FakeClient({})  # C absent → not a learned_pattern
        stats = _cascade_confidence(client, "A", success=True, now=datetime.now())
        assert stats["entities_updated"] == 0
        assert stats["cascades_prevented"] == 1

    def test_opt_out_gate(self, tmp_path, monkeypatch):
        from memory.vector_memory.server import _cascade_confidence

        tmp_db = tmp_path / "link_registry.db"
        real_cls, LinkType = _registry_factory(tmp_db, monkeypatch)
        _link(
            real_cls(db_path=str(tmp_db)),
            "semantic:vector-memory:A",
            "semantic:vector-memory:B",
            LinkType.SUPPORTS,
        )
        monkeypatch.setenv("MEMORY_APPLY_CASCADE_DISABLE", "1")

        client = _FakeClient({"B": {"confidence": 0.70, "succ": 0.0, "fail": 0.0}})
        stats = _cascade_confidence(client, "A", success=True, now=datetime.now())
        assert stats["entities_updated"] == 0
        assert client.set_calls == []
