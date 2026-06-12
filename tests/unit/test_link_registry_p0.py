"""P0/P3 regression (roadmap 260612 LinkRegistry): валидация unified-ID,
delete-журнал, stats-гигиена, rebuild, trace fail-soft.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.memory.orchestrator.link_registry import LinkRegistry, LinkType

pytestmark = pytest.mark.unit

A = "semantic:vector-memory:aaa"
B = "episodic:memory-ai:bbb"
C = "learning:skill-learning:ccc"


@pytest.fixture
def reg(tmp_path: Path) -> LinkRegistry:
    return LinkRegistry(db_path=str(tmp_path / "links.db"))


def _q(reg: LinkRegistry, sql: str) -> list:
    conn = sqlite3.connect(reg.db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_raw_uuid_rejected(reg: LinkRegistry) -> None:
    with pytest.raises(ValueError, match="unified ID"):
        reg.create_link("49362a90-9aaf-48d9-87b4-4fe64fc19faa", A, LinkType.SUPPORTS)
    with pytest.raises(ValueError, match="unified ID"):
        reg.create_link(A, "two:parts", LinkType.SUPPORTS)
    with pytest.raises(ValueError, match="unified ID"):
        reg.create_links_batch([("bare", A, LinkType.MIRRORS, 0.9)])


def test_delete_is_journaled_and_stats_purged(reg: LinkRegistry) -> None:
    reg.create_link(A, B, LinkType.SUPPORTS)
    reg.create_link(A, C, LinkType.EXTENDS)
    deleted = reg.delete_links_for_entity(A, changed_by="ttl-cascade", reason="ttl expired")
    assert deleted == 2

    actions = dict(_q(reg, "SELECT action, COUNT(*) FROM link_history GROUP BY action"))
    assert actions.get("create") == 2
    assert actions.get("delete") == 2  # P0.3: удаления журналируются

    # P0.2: сущности без рёбер не живут в stats
    assert _q(reg, "SELECT COUNT(*) FROM link_stats")[0][0] == 0


def test_batch_create_journaled(reg: LinkRegistry) -> None:
    reg.create_links_batch([(A, B, LinkType.MIRRORS, 1.0), (B, C, LinkType.MIRRORS, 1.0)])
    actions = dict(_q(reg, "SELECT action, COUNT(*) FROM link_history GROUP BY action"))
    assert actions.get("create") == 2
    # stats наполнены для всех концов
    assert _q(reg, "SELECT COUNT(*) FROM link_stats")[0][0] == 3


def test_rebuild_stats_heals_drift(reg: LinkRegistry) -> None:
    reg.create_link(A, B, LinkType.SUPPORTS)
    # имитация легаси-дрейфа: orphan-строка + кривой счётчик
    conn = sqlite3.connect(reg.db_path)
    conn.execute(
        "INSERT OR REPLACE INTO link_stats VALUES ('ghost:x:y', 9, 9, 0.5, '2026-01-01')"
    )
    conn.execute("UPDATE link_stats SET outgoing_count = 42 WHERE entity_id = ?", (A,))
    conn.commit()
    conn.close()

    result = reg.rebuild_stats()
    assert result["rebuilt"] == 2  # только реальные концы A и B
    rows = dict(_q(reg, "SELECT entity_id, outgoing_count FROM link_stats"))
    assert rows == {A: 1, B: 0}


def test_retired_types_absent() -> None:
    assert len(LinkType) == 8
    assert not hasattr(LinkType, "BASED_ON")
    assert not hasattr(LinkType, "GRAPH_NODE")


def test_trace_failsoft(reg: LinkRegistry, monkeypatch: pytest.MonkeyPatch) -> None:
    # сломанный trace_log не должен ронять CRUD
    import src.memory.infrastructure.trace_log as tl

    def boom(*a, **kw):
        raise RuntimeError("sink down")

    monkeypatch.setattr(tl, "write_trace", boom)
    link = reg.create_link(A, B, LinkType.SUPPORTS)
    assert link.link_id
