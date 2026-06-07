"""Unit tests for the cross-store sync core (§26 P3, D3.2+D3.3).

Covers the pure planning core: unified-id mapping, canonical selection via
ConflictResolver(SOURCE_PRIORITY), MIRRORS link-plan construction (direction,
intra-store mirrors, skip-unmappable), and summary/report rendering. The CLI
(link_registry writes, store scanning) is exercised by the live run.
"""

from __future__ import annotations

import pytest

from src.memory.orchestrator.cross_store_index import StoreRecord
from src.memory.orchestrator.cross_store_sync import (
    STORE_PRIORITY,
    MirrorLink,
    build_sync_plan,
    choose_canonical,
    render_sync_report,
    summarize_plan,
    unified_id_for,
)

pytestmark = pytest.mark.unit


def _rec(store: str, item_id: str, content_hash: str = "h") -> StoreRecord:
    return StoreRecord(store=store, item_id=item_id, content_hash=content_hash)


class TestUnifiedIdFor:
    def test_known_stores_map(self):
        assert unified_id_for(_rec("learned_patterns", "p1")) == "semantic:vector-memory:p1"
        assert unified_id_for(_rec("memory_ai", "m1")) == "episodic:memory-ai:m1"
        assert unified_id_for(_rec("skill_learning", "s1")) == "learning:skill-learning:s1"
        assert unified_id_for(_rec("wiki", "w1")) == "wiki:obsidian-vault:w1"

    def test_unknown_store_is_none(self):
        assert unified_id_for(_rec("pdf_docs", "x")) is None

    def test_illegal_identifier_is_none(self):
        # space is not in the unified-id identifier grammar -> None, not a crash
        assert unified_id_for(_rec("memory_ai", "has space")) is None


class TestChooseCanonical:
    def test_priority_order(self):
        # wiki beats learned_patterns beats skill_learning beats memory_ai
        recs = [
            _rec("memory_ai", "m"),
            _rec("skill_learning", "s"),
            _rec("learned_patterns", "p"),
            _rec("wiki", "w"),
        ]
        _, store = choose_canonical(recs)
        assert store == "wiki"

    def test_learned_beats_memory(self):
        _, store = choose_canonical([_rec("memory_ai", "m"), _rec("learned_patterns", "p")])
        assert store == "learned_patterns"

    def test_priority_list_shape(self):
        assert STORE_PRIORITY[0] == "wiki"
        assert STORE_PRIORITY[-1] == "memory_ai"


class TestBuildSyncPlan:
    def test_two_store_dup_one_mirror(self):
        dups = [("h", [_rec("learned_patterns", "p"), _rec("memory_ai", "m")])]
        plan = build_sync_plan(dups)
        assert len(plan["links"]) == 1
        link = plan["links"][0]
        # mirror (memory_ai) -> canonical (learned_patterns)
        assert link.mirror_uid == "episodic:memory-ai:m"
        assert link.canonical_uid == "semantic:vector-memory:p"
        assert plan["conflicts"][0]["canonical_store"] == "learned_patterns"

    def test_three_store_two_mirrors_to_wiki(self):
        dups = [
            (
                "h",
                [_rec("memory_ai", "m"), _rec("learned_patterns", "p"), _rec("wiki", "w")],
            )
        ]
        plan = build_sync_plan(dups)
        assert len(plan["links"]) == 2
        assert all(lk.canonical_uid == "wiki:obsidian-vault:w" for lk in plan["links"])
        mirrors = {lk.mirror_uid for lk in plan["links"]}
        assert mirrors == {"episodic:memory-ai:m", "semantic:vector-memory:p"}

    def test_intra_store_extra_becomes_mirror(self):
        # 2 memory_ai + 1 learned_patterns: canonical=learned, both memory_ai mirror it
        dups = [
            ("h", [_rec("memory_ai", "m1"), _rec("memory_ai", "m2"), _rec("learned_patterns", "p")])
        ]
        plan = build_sync_plan(dups)
        assert len(plan["links"]) == 2
        assert all(lk.canonical_uid == "semantic:vector-memory:p" for lk in plan["links"])

    def test_unmappable_group_skipped(self):
        dups = [("h", [_rec("pdf_docs", "a"), _rec("pdf_docs", "b")])]
        plan = build_sync_plan(dups)
        assert plan["links"] == []
        assert plan["skipped"] == ["h"]

    def test_mirror_link_is_frozen_dataclass(self):
        link = MirrorLink("a", "b", "h")
        with pytest.raises(Exception):
            link.mirror_uid = "c"  # type: ignore[misc]


class TestSummaryAndReport:
    def test_summary_counts(self):
        dups = [
            ("h1", [_rec("learned_patterns", "p"), _rec("memory_ai", "m")]),
            ("h2", [_rec("wiki", "w"), _rec("memory_ai", "m2")]),
        ]
        plan = build_sync_plan(dups)
        s = summarize_plan(plan)
        assert s["mirror_links"] == 2
        assert s["conflict_groups"] == 2
        assert s["canonical_by_store"] == {"learned_patterns": 1, "wiki": 1}

    def test_report_contains_sections(self):
        dups = [("h1", [_rec("learned_patterns", "p"), _rec("memory_ai", "m")])]
        plan = build_sync_plan(dups)
        out = render_sync_report(plan, summarize_plan(plan), "20260605_000000")
        assert "MIRRORS links" in out
        assert "Conflict resolution audit" in out
        assert "dry-run" in out

    def test_report_applied_marker(self):
        out = render_sync_report(
            {"links": [], "conflicts": [], "skipped": []},
            summarize_plan({"links": [], "conflicts": [], "skipped": []}),
            "ts",
            applied=True,
        )
        assert "APPLIED" in out
