"""Unit tests for the light->full learned_patterns normalizer (Qdrant-independent)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _ROOT / "scripts" / "normalize_light_patterns.py"


def _load():
    spec = importlib.util.spec_from_file_location("normalize_light_patterns", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


N = _load()


def _light(content, category, importance=0.7, original_id="orig-1"):
    return {"original_id": original_id, "content": content, "category": category,
            "importance": importance, "tags": "[]", "source": "memory_ai_session",
            "created_at": "2026-04-04T20:00:00"}


def test_is_light():
    assert N.is_light(_light("c", "decision")) is True
    assert N.is_light({"pattern_id": "x", "content": "c"}) is False
    assert N.is_light({"content": "c"}) is False  # neither field


def test_derive_name():
    assert N.derive_name("1c-credentials | # full doc here") == "1c-credentials"
    assert N.derive_name("single line note") == "single line note"
    assert N.derive_name("first\nsecond") == "first"
    assert len(N.derive_name("x" * 200)) == 80


def test_parse_tags():
    assert N.parse_tags("[]") == []
    assert N.parse_tags('["a", "b"]') == ["a", "b"]
    assert N.parse_tags(["x"]) == ["x"]
    assert N.parse_tags("not json") == []
    assert N.parse_tags(None) == []


def test_normalize_payload_maps_category_and_preserves_provenance():
    p = N.normalize_payload("pt-1", _light("User prefers Qdrant", "preference", importance=0.8),
                            now_iso="2026-06-02T00:00:00")
    assert p["pattern_id"] == "pt-1"
    assert p["pattern_type"] == "workflow-pattern"   # preference -> workflow-pattern
    assert p["confidence"] == 0.8                     # denorm = importance
    assert p["succ"] == 0.0 and p["fail"] == 0.0      # no fabricated evidence (seed=0)
    assert p["content"] == "User prefers Qdrant"
    assert p["tags"] == []                            # "[]" string -> real list
    assert p["metadata"]["original_category"] == "preference"
    assert p["metadata"]["original_importance"] == 0.8
    assert p["metadata"]["original_id"] == "orig-1"
    assert p["expired_at"] is None and p["version"] == 1


def test_normalize_payload_skips_unmapped_category():
    assert N.normalize_payload("x", _light("Session 2026...", "session_summary"),
                               now_iso="2026-06-02T00:00:00") is None


def test_seed_importance_injects_evidence():
    # seed_importance>0 -> succ/fail reflect the importance ratio (synthetic pseudo-obs)
    p = N.normalize_payload("x", _light("c", "decision", importance=0.75),
                            now_iso="2026-06-02T00:00:00", seed_importance=4)
    assert p["succ"] == pytest.approx(3.0)   # 0.75 * 4
    assert p["fail"] == pytest.approx(1.0)   # 0.25 * 4


def test_build_plan_counts():
    pts = [
        SimpleNamespace(id="a", payload=_light("x", "decision")),
        SimpleNamespace(id="b", payload=_light("y", "session_summary")),       # skip
        SimpleNamespace(id="c", payload={"pattern_id": "c", "content": "z"}),  # rich, untouched
    ]
    plan = N.build_plan(pts, now_iso="2026-06-02T00:00:00", seed_importance=0)
    assert plan["total"] == 3
    assert plan["rich_untouched"] == 1
    assert len(plan["normalize"]) == 1 and plan["normalize"][0]["id"] == "a"
    assert len(plan["skipped"]) == 1 and plan["skipped"][0]["category"] == "session_summary"
