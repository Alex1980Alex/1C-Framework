"""Integration guard for §22 review finding #1 — learned_patterns always surface.

Covers:
- _search_learned_patterns: overlap hit → tagged _collection='learned_patterns'
- _search_learned_patterns: non-overlapping query → []
- _search_learned_patterns: QdrantClient raising → fail-soft []
- REGRESSION GUARD (#1): search_qdrant returns learned_patterns entries
  EVEN WHEN the semantic path returns a hit (TEI healthy scenario).
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Load memory-first-hook via importlib (hyphen-named, outside package tree)
# ---------------------------------------------------------------------------

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
_HOOK_PATH = _HOOKS_DIR / "memory-first-hook.py"


def _load_mfh(monkeypatch):
    """Load memory-first-hook with heavy deps stubbed out so exec_module succeeds."""
    # Stub 'base' module (imported at top-level in the hook)
    if "base" not in sys.modules:
        base_stub = types.ModuleType("base")

        class _FakeBase:
            pass

        class _FakeInput:
            pass

        class _FakeOutput:
            pass

        base_stub.BaseHook = _FakeBase
        base_stub.HookInput = _FakeInput
        base_stub.HookOutput = _FakeOutput
        monkeypatch.setitem(sys.modules, "base", base_stub)

    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))

    spec = importlib.util.spec_from_file_location("memory_first_hook", _HOOK_PATH)
    assert spec and spec.loader, f"Could not create spec for {_HOOK_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Shared fake Qdrant primitives
# ---------------------------------------------------------------------------

class _FakePayload(dict):
    pass


class _FakePoint:
    def __init__(self, payload: dict, id: str = "p1"):
        self.payload = _FakePayload(payload)
        self.id = id


def _make_qdrant_stub(points: list[_FakePoint]):
    """Return a fake QdrantClient class whose scroll() yields the given points."""

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        def scroll(self, **kwargs):
            return (points, None)

    return _FakeClient


# ---------------------------------------------------------------------------
# Tests for _search_learned_patterns
# ---------------------------------------------------------------------------

class TestSearchLearnedPatterns:
    def test_overlap_hit_tagged(self, monkeypatch):
        """Matching tokens → result tagged _collection='learned_patterns'."""
        mfh = _load_mfh(monkeypatch)

        fake_client = _make_qdrant_stub(
            [_FakePoint({"content": "alpha beta gamma", "category": "pattern"}, id="p1")]
        )
        import qdrant_client as _qc
        monkeypatch.setattr(_qc, "QdrantClient", fake_client)
        # Also patch inside the module's lazy import namespace
        monkeypatch.setitem(sys.modules, "qdrant_client", _qc)

        query_tokens = set(mfh.tokenize("alpha beta"))
        import time
        results = mfh._search_learned_patterns(query_tokens, time.monotonic(), limit=10)

        assert len(results) == 1
        assert results[0]["_collection"] == "learned_patterns"
        assert results[0]["id"] == "p1"
        assert results[0]["score"] >= mfh.SCORE_THRESHOLD

    def test_non_overlapping_returns_empty(self, monkeypatch):
        """No token overlap → empty list."""
        mfh = _load_mfh(monkeypatch)

        fake_client = _make_qdrant_stub(
            [_FakePoint({"content": "completely unrelated xyz", "category": "pattern"}, id="p2")]
        )
        import qdrant_client as _qc
        monkeypatch.setattr(_qc, "QdrantClient", fake_client)

        query_tokens = set(mfh.tokenize("alpha beta"))
        import time
        results = mfh._search_learned_patterns(query_tokens, time.monotonic(), limit=10)

        assert results == []

    def test_qdrant_raises_fail_soft(self, monkeypatch):
        """QdrantClient raising any exception → fail-soft, returns []."""
        mfh = _load_mfh(monkeypatch)

        class _BoomClient:
            def __init__(self, **kwargs):
                raise ConnectionError("qdrant down")

        import qdrant_client as _qc
        monkeypatch.setattr(_qc, "QdrantClient", _BoomClient)

        query_tokens = set(mfh.tokenize("alpha beta"))
        import time
        results = mfh._search_learned_patterns(query_tokens, time.monotonic(), limit=10)

        assert results == []


# ---------------------------------------------------------------------------
# REGRESSION GUARD — §22 finding #1
# ---------------------------------------------------------------------------

class TestSearchQdrantLearnedPatternsAlwaysSurface:
    """Ensure learned_patterns appear in search_qdrant output even when the
    semantic path succeeds (TEI healthy). This is the exact bug from finding #1:
    the old code early-returned from semantic path, so record_surfaced() got []."""

    def test_learned_patterns_present_when_semantic_hits(self, monkeypatch):
        # --- Load module ---
        mfh = _load_mfh(monkeypatch)

        # --- Stub semantic imports so TEI path returns a hit ---
        semantic_mod = types.ModuleType("shared.semantic_search")

        def _fake_embed(text, timeout=1.5):
            return [0.1] * 10  # truthy non-empty vector

        def _fake_search(collection, embedding, limit=5, timeout=1.0):
            # skill_library collection uses skill_name/description keys
            return [
                {
                    "id": "sem1",
                    "score": 0.85,
                    "payload": {
                        "skill_name": "some-skill",
                        "description": "Semantic Hit description",
                    },
                }
            ]

        semantic_mod.embed_query_tei = _fake_embed
        semantic_mod.search_qdrant_semantic = _fake_search

        # Patch both the top-level shared package and the dotted name
        shared_pkg = sys.modules.get("shared") or types.ModuleType("shared")
        monkeypatch.setitem(sys.modules, "shared", shared_pkg)
        monkeypatch.setitem(sys.modules, "shared.semantic_search", semantic_mod)

        # --- Stub QdrantClient so learned_patterns scroll returns a hit ---
        fake_client = _make_qdrant_stub(
            [_FakePoint({"content": "alpha beta pattern", "category": "pattern"}, id="lp1")]
        )
        import qdrant_client as _qc
        monkeypatch.setattr(_qc, "QdrantClient", fake_client)

        # --- Call search_qdrant with tokens overlapping learned_patterns content ---
        query_tokens = set(mfh.tokenize("alpha beta"))
        results = mfh.search_qdrant(query_tokens, limit=10, prompt="alpha beta")

        ids = [r.get("id") for r in results]
        collections = [r.get("_collection") for r in results]

        # Semantic hit must be present
        assert "sem1" in ids, f"Semantic result missing from {ids}"
        # learned_patterns hit must ALSO be present (the §22 fix)
        assert "lp1" in ids, (
            f"learned_patterns entry 'lp1' missing from results — "
            f"P1 reinforcement loop would be a no-op. ids={ids}"
        )
        assert "learned_patterns" in collections, (
            f"No _collection='learned_patterns' in results. collections={collections}"
        )
