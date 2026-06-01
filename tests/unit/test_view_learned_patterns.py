"""Unit tests for the learned_patterns viewer filters (Qdrant-independent)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _ROOT / "scripts" / "view_learned_patterns.py"


def _load():
    spec = importlib.util.spec_from_file_location("view_learned_patterns", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V = _load()


def _pt(pid, content, *, ptype=None, category=None, created="2026-01-01"):
    pl = {"content": content, "created_at": created}
    if ptype:
        pl["pattern_type"] = ptype
    if category:
        pl["category"] = category
    return SimpleNamespace(id=pid, payload=pl)


def test_pattern_type_and_content_extraction():
    assert V.pattern_type({"pattern_type": "code-convention"}) == "code-convention"
    assert V.pattern_type({"category": "decision"}) == "decision"
    assert V.pattern_type({}) == "?"
    assert V.pattern_content({"description": "d"}) == "d"
    assert V.pattern_content({"content": "c", "description": "d"}) == "c"


def test_matches_type_and_grep():
    pl = {"content": "def calculate_rrf_score()", "pattern_type": "code-convention"}
    assert V.matches(pl, type_filter="code-convention", min_conf=0.0, grep=None)
    assert not V.matches(pl, type_filter="decision", min_conf=0.0, grep=None)
    assert V.matches(pl, type_filter=None, min_conf=0.0, grep="RRF")  # case-insensitive
    assert not V.matches(pl, type_filter=None, min_conf=0.0, grep="neo4j")


def test_build_rows_filters_and_sorts():
    points = [
        _pt("b", "rrf score", ptype="code-convention", created="2026-03-01"),
        _pt("a", "rrf search", ptype="code-convention", created="2026-01-01"),
        _pt("c", "a decision", category="decision", created="2026-02-01"),
    ]
    rows = V.build_rows(points, type_filter="code-convention", min_conf=0.0, grep=None)
    assert [r["id"] for r in rows] == ["a", "b"]  # filtered to type, sorted by created_at
    rows_grep = V.build_rows(points, type_filter=None, min_conf=0.0, grep="decision")
    assert [r["id"] for r in rows_grep] == ["c"]


def test_render_preview_vs_full():
    long = "x" * 500
    rows = [{"id": "abcdef12", "type": "t", "confidence": 0.6, "effective_confidence": 0.7,
             "application_count": 0, "created_at": "2026-01-01", "archived": False, "content": long}]
    preview = V.render(rows, 1, full=False, label="L")
    full = V.render(rows, 1, full=True, label="L")
    assert "…" in preview and len(long) > 300
    assert long in full  # full body present uncut
    assert "eff_conf=0.700" in preview


def test_render_archived_flag():
    rows = [{"id": "abcdef12", "type": "t", "confidence": None, "effective_confidence": None,
             "application_count": 1, "created_at": "2026-01-01", "archived": True, "content": "c"}]
    out = V.render(rows, 1, full=True, label="L")
    assert "[ARCHIVED]" in out
    assert "eff_conf=—" in out  # None confidence renders as dash
