"""Unit tests for .claude/hooks/shared/reflection.py (§26 P2 D2.1 + D2.3).

Covers acceptance criteria:
- M episodes on one topic → 1 semantic pattern (not M), with DERIVES_FROM
  links to all M sources
- below-trigger cluster → 0 patterns; theta (importance-sum) alt trigger works
- dry-run → plan computed, no upsert, no links
- content_hash dedup: rerun → 0 new
- distinct topics → separate clusters, only triggered consolidate
- session_summary excluded from episodes
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"


def _load() -> Any:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(
        "reflection_mod", _HOOKS_DIR / "shared" / "reflection.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


rf = _load()


class FakeClient:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    def retrieve(self, collection_name: str, ids: list[str]) -> list[Any]:
        return [self.store[i] for i in ids if i in self.store]

    def upsert(self, collection_name: str, points: list[Any]) -> None:
        for p in points:
            self.store[p.id] = p


def _embed(_t: str) -> list[float]:
    return [0.3] * 8


def _rows(*specs: tuple[str, str, float]) -> list[dict[str, Any]]:
    """Build episodic rows: (id, content, importance) with category 'decision'."""
    return [
        {
            "id": rid,
            "content": content,
            "importance": imp,
            "category": "decision",
            "created_at": "2099",
        }
        for rid, content, imp in specs
    ]


def test_four_same_topic_episodes_consolidate_to_one_with_links() -> None:
    rows = _rows(
        (
            "e1",
            "always read attribute via ОбщегоНазначения helper not direct reference access",
            0.6,
        ),
        (
            "e2",
            "read attribute via ОбщегоНазначения helper avoid direct reference object load",
            0.7,
        ),
        (
            "e3",
            "attribute read should use ОбщегоНазначения helper not direct reference access path",
            0.8,
        ),
        (
            "e4",
            "use ОбщегоНазначения helper for attribute read avoid direct reference loading",
            0.5,
        ),
    )
    client = FakeClient()
    links: list[tuple[str, str]] = []
    stats = rf.reflect(
        rows=rows,
        client=client,
        embed=_embed,
        dry_run=False,
        link_fn=lambda pid, sid: links.append((pid, sid)),
        min_cluster=3,
        sim_threshold=0.3,
    )
    assert stats["clusters_triggered"] == 1
    assert stats["created"] == 1  # one pattern, not four
    assert len(client.store) == 1
    assert len(links) == 4  # DERIVES_FROM to each source episode
    target_ids = {sid for _, sid in links}
    assert target_ids == {"e1", "e2", "e3", "e4"}


def test_below_min_cluster_not_triggered() -> None:
    rows = _rows(
        ("e1", "topic alpha shared tokens here for overlap matching test alpha", 0.5),
        ("e2", "topic alpha shared tokens here for overlap matching test alpha too", 0.5),
    )
    client = FakeClient()
    stats = rf.reflect(
        rows=rows, client=client, embed=_embed, dry_run=False, min_cluster=3, sim_threshold=0.3
    )
    assert stats["clusters_triggered"] == 0
    assert stats["created"] == 0


def test_theta_importance_trigger() -> None:
    rows = _rows(
        ("e1", "topic beta with enough shared overlap tokens beta beta sample", 0.9),
        ("e2", "topic beta with enough shared overlap tokens beta beta example", 0.9),
    )
    client = FakeClient()
    stats = rf.reflect(
        rows=rows,
        client=client,
        embed=_embed,
        dry_run=False,
        min_cluster=5,
        importance_theta=1.5,
        sim_threshold=0.3,
    )
    assert stats["clusters_triggered"] == 1  # size<5 but sum importance 1.8 >= 1.5
    assert stats["created"] == 1


def test_dry_run_no_writes_no_links() -> None:
    rows = _rows(
        ("e1", "gamma topic shared overlap tokens gamma gamma sample words here", 0.6),
        ("e2", "gamma topic shared overlap tokens gamma gamma example words here", 0.6),
        ("e3", "gamma topic shared overlap tokens gamma gamma another words here", 0.6),
    )
    client = FakeClient()
    links: list[Any] = []
    stats = rf.reflect(
        rows=rows,
        client=client,
        embed=_embed,
        dry_run=True,
        link_fn=lambda p, s: links.append((p, s)),
        min_cluster=3,
        sim_threshold=0.3,
    )
    assert stats["created"] == 1  # planned
    assert len(client.store) == 0  # nothing written
    assert len(links) == 0  # links only on real upsert


def test_rerun_idempotent() -> None:
    rows = _rows(
        ("e1", "delta topic overlap tokens delta delta words sample here now", 0.6),
        ("e2", "delta topic overlap tokens delta delta words example here now", 0.6),
        ("e3", "delta topic overlap tokens delta delta words another here now", 0.6),
    )
    client = FakeClient()
    s1 = rf.reflect(
        rows=rows, client=client, embed=_embed, dry_run=False, min_cluster=3, sim_threshold=0.3
    )
    s2 = rf.reflect(
        rows=rows, client=client, embed=_embed, dry_run=False, min_cluster=3, sim_threshold=0.3
    )
    assert s1["created"] == 1 and s2["created"] == 0 and s2["skipped_dup"] == 1


def test_distinct_topics_separate_clusters() -> None:
    rows = _rows(
        ("a1", "apple fruit red sweet orchard harvest apple apple basket here", 0.6),
        ("a2", "apple fruit red sweet orchard harvest apple apple crate here", 0.6),
        ("a3", "apple fruit red sweet orchard harvest apple apple bushel here", 0.6),
        ("b1", "rocket space launch orbit fuel rocket rocket payload mission now", 0.6),
        ("b2", "rocket space launch orbit fuel rocket rocket payload booster now", 0.6),
    )
    client = FakeClient()
    stats = rf.reflect(
        rows=rows, client=client, embed=_embed, dry_run=False, min_cluster=3, sim_threshold=0.3
    )
    assert stats["clusters_found"] == 2  # apple + rocket
    assert stats["clusters_triggered"] == 1  # only apple has >=3
    assert stats["created"] == 1


def test_session_summary_excluded(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "m.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE important_messages (id TEXT, content TEXT, importance REAL, "
        "category TEXT, created_at TEXT, updated_at TEXT, metadata TEXT, tags TEXT)"
    )
    conn.execute(
        "INSERT INTO important_messages (id, content, importance, category) VALUES (?,?,?,?)",
        ("s1", "Session 2099 did stuff", 0.7, "session_summary"),
    )
    conn.execute(
        "INSERT INTO important_messages (id, content, importance, category) VALUES (?,?,?,?)",
        ("f1", "a real decision fact here", 0.7, "decision"),
    )
    conn.commit()
    conn.close()
    eps = rf.read_episodes(db_path=db)
    cats = {e["category"] for e in eps}
    assert "session_summary" not in cats
    assert "decision" in cats
