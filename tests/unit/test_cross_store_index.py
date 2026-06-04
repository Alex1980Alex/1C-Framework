"""Unit tests for the cross-store content_hash index core (§26 P3, D3.1).

Covers the pure, I/O-free core: reverse-index build, cross-store duplicate
classification (>=2 distinct stores, not intra-store repeats), summary metrics
(incl. cross_store_dup_rate), and report rendering. Store scanners (Qdrant/
SQLite/JSONL/wiki I/O) live in ``scripts/cross_store_index.py`` and are exercised
by the live run, not here.
"""

from __future__ import annotations

import pytest

from src.memory.orchestrator.cross_store_index import (
    StoreRecord,
    build_index,
    find_cross_store_dups,
    render_report,
    summarize,
)

pytestmark = pytest.mark.unit


def _rec(store: str, item_id: str, content_hash: str, preview: str = "") -> StoreRecord:
    return StoreRecord(store=store, item_id=item_id, content_hash=content_hash, preview=preview)


class TestBuildIndex:
    def test_groups_by_hash(self):
        recs = [_rec("learned_patterns", "1", "aaa"), _rec("memory_ai", "2", "aaa")]
        index = build_index(recs)
        assert set(index) == {"aaa"}
        assert len(index["aaa"]) == 2

    def test_skips_empty_hash(self):
        index = build_index([_rec("memory_ai", "1", ""), _rec("memory_ai", "2", "bbb")])
        assert set(index) == {"bbb"}

    def test_empty_input(self):
        assert build_index([]) == {}


class TestFindCrossStoreDups:
    def test_detects_two_store_dup(self):
        recs = [_rec("learned_patterns", "1", "h"), _rec("memory_ai", "2", "h")]
        dups = find_cross_store_dups(build_index(recs))
        assert len(dups) == 1
        assert dups[0][0] == "h"

    def test_intra_store_repeat_is_not_cross_store(self):
        # same hash, same store, twice -> NOT a cross-store duplicate
        recs = [_rec("memory_ai", "1", "h"), _rec("memory_ai", "2", "h")]
        assert find_cross_store_dups(build_index(recs)) == []

    def test_single_store_hash_ignored(self):
        recs = [_rec("learned_patterns", "1", "h")]
        assert find_cross_store_dups(build_index(recs)) == []

    def test_sorted_by_store_span_desc(self):
        recs = [
            _rec("learned_patterns", "1", "two"),
            _rec("memory_ai", "2", "two"),
            _rec("learned_patterns", "3", "three"),
            _rec("memory_ai", "4", "three"),
            _rec("skill_learning", "5", "three"),
        ]
        dups = find_cross_store_dups(build_index(recs))
        # "three" spans 3 stores -> ranked before "two" (2 stores)
        assert [h for h, _ in dups] == ["three", "two"]


class TestSummarize:
    def test_counts_and_rate(self):
        recs = [
            _rec("learned_patterns", "1", "shared"),
            _rec("memory_ai", "2", "shared"),
            _rec("memory_ai", "3", "lonely"),
        ]
        index = build_index(recs)
        dups = find_cross_store_dups(index)
        s = summarize(recs, index, dups)
        assert s["total_records"] == 3
        assert s["by_store"] == {"learned_patterns": 1, "memory_ai": 2}
        assert s["unique_hashes"] == 2
        assert s["cross_store_dup_count"] == 1
        assert s["cross_store_affected_records"] == 2
        assert s["cross_store_dup_rate"] == round(1 / 2, 4)

    def test_intra_store_dups_counted(self):
        recs = [_rec("memory_ai", "1", "h"), _rec("memory_ai", "2", "h")]
        index = build_index(recs)
        s = summarize(recs, index, find_cross_store_dups(index))
        assert s["intra_store_dups"] == 1
        assert s["cross_store_dup_count"] == 0

    def test_empty_safe(self):
        s = summarize([], {}, [])
        assert s["total_records"] == 0
        assert s["cross_store_dup_rate"] == 0.0


class TestRenderReport:
    def test_no_dups_message(self):
        out = render_report(summarize([], {}, []), [], "20260603_000000")
        assert "no fact found in two or more stores" in out.lower()

    def test_lists_dup_group_and_stores(self):
        recs = [_rec("learned_patterns", "p1", "h", "cyrillic пример"), _rec("wiki", "w1", "h")]
        index = build_index(recs)
        dups = find_cross_store_dups(index)
        out = render_report(summarize(recs, index, dups), dups, "20260603_000000")
        assert "`h`" in out
        assert "learned_patterns" in out and "wiki" in out
        assert "p1" in out and "w1" in out

    def test_store_errors_section(self):
        out = render_report(summarize([], {}, []), [], "ts", {"learned_patterns": "Qdrant down"})
        assert "Skipped stores" in out
        assert "Qdrant down" in out
