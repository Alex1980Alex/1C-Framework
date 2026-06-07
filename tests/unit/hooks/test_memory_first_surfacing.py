"""Tests for §24 P0 — semantic surfacing + confidence-gating + archived-exclude.

Covers:
- _pattern_effective_confidence: graceful degrade when fields missing
- _pattern_score_gate: archived hard-exclude (with/without MEMORY_INCLUDE_ARCHIVED)
- _pattern_score_gate: noise floor hard-exclude (eff < MIN_SURFACE_CONF)
- _pattern_score_gate: healthy pattern -> floored-multiply score
- _pattern_score_gate: new pattern (prior) -> NOT crushed, floored-multiply
- _pattern_score_gate: floor protection (eff between MIN_SURFACE_CONF and CONF_FLOOR)
- _search_learned_patterns: overlap hit -> tagged _collection='learned_patterns'
- _search_learned_patterns: non-overlapping query -> []
- _search_learned_patterns: QdrantClient raising -> fail-soft []
- _search_learned_patterns: archived pattern excluded by gate in fallback path
- REGRESSION GUARD (section 24): search_qdrant returns learned_patterns entries
  via SEMANTIC path when TEI is up (learned_patterns now in SEMANTIC_COLLECTIONS).
- TEI-down fallback: token-overlap runs when embed returns empty.
- Archived pattern excluded from semantic path.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest

# Several tests import qdrant_client directly; skip the module when the qdrant
# extra is not installed (unit-test CI env).
pytest.importorskip("qdrant_client")

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Load memory-first-hook via importlib (hyphen-named, outside package tree)
# ---------------------------------------------------------------------------

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
_HOOK_PATH = _HOOKS_DIR / "memory-first-hook.py"


def _load_mfh(monkeypatch):
    """Load memory-first-hook with heavy deps stubbed out so exec_module succeeds."""
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


# Shared test timestamp: recent enough that time-decay is near-zero
_T0 = datetime(2026, 1, 1).isoformat()


# ---------------------------------------------------------------------------
# Tests for _pattern_effective_confidence
# ---------------------------------------------------------------------------


class TestPatternEffectiveConfidence:
    def test_graceful_degrade_missing_fields(self, monkeypatch):
        """payload missing all fields -> returns a float, no raise."""
        mfh = _load_mfh(monkeypatch)
        result = mfh._pattern_effective_confidence({})
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_graceful_degrade_import_error(self, monkeypatch):
        """Import failure -> falls back to payload.confidence as float, no raise."""
        mfh = _load_mfh(monkeypatch)
        # Poison the sub-module so lazy import raises
        monkeypatch.setitem(
            sys.modules,
            "memory.vector_memory.confidence",
            None,  # type: ignore[arg-type]
        )
        result = mfh._pattern_effective_confidence({"confidence": 0.42})
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Tests for _pattern_score_gate
# ---------------------------------------------------------------------------


class TestPatternScoreGate:
    def test_archived_hard_exclude(self, monkeypatch):
        """expired_at set + no env override -> None (hard-exclude)."""
        mfh = _load_mfh(monkeypatch)
        payload = {"expired_at": _T0, "succ": 5.0, "fail": 0.0, "last_decay_at": _T0}
        result = mfh._pattern_score_gate(payload, 1.0)
        assert result is None

    def test_archived_included_with_env(self, monkeypatch):
        """MEMORY_INCLUDE_ARCHIVED=1 -> archived pattern is NOT excluded."""
        mfh = _load_mfh(monkeypatch)
        monkeypatch.setenv("MEMORY_INCLUDE_ARCHIVED", "1")
        payload = {"expired_at": _T0, "succ": 5.0, "fail": 0.0, "last_decay_at": _T0}
        result = mfh._pattern_score_gate(payload, 1.0)
        assert result is not None

    def test_low_conf_noise_floor(self, monkeypatch):
        """succ=0, fail=50 -> eff ~= 7/60 ~= 0.117 < MIN_SURFACE_CONF=0.15 -> None."""
        mfh = _load_mfh(monkeypatch)
        # Beta posterior: (PRIOR_SUCCESS+0) / (PRIOR_SUCCESS+PRIOR_FAILURE+0+50)
        # = 7 / (7+3+50) = 7/60 ~= 0.117
        payload = {"succ": 0.0, "fail": 50.0, "last_decay_at": _T0}
        result = mfh._pattern_score_gate(payload, 1.0)
        assert result is None

    def test_healthy_pattern_floored_multiply(self, monkeypatch):
        """succ=5, fail=0 -> eff = 12/15 = 0.80 -> score = base * 0.80."""
        mfh = _load_mfh(monkeypatch)
        # Beta posterior: (7+5) / (7+3+5+0) = 12/15 = 0.80
        payload = {"succ": 5.0, "fail": 0.0, "last_decay_at": _T0}
        result = mfh._pattern_score_gate(payload, 1.0)
        assert result is not None
        assert abs(result - 0.80) < 0.05, f"Expected ~0.80, got {result}"

    def test_new_pattern_prior_not_crushed(self, monkeypatch):
        """New pattern (succ=0, fail=0) -> prior mean 0.70 -> base*0.70, NOT None."""
        mfh = _load_mfh(monkeypatch)
        # Beta prior mean: PRIOR_SUCCESS / (PRIOR_SUCCESS+PRIOR_FAILURE) = 7/10 = 0.70
        payload = {"succ": 0.0, "fail": 0.0, "last_decay_at": _T0}
        result = mfh._pattern_score_gate(payload, 1.0)
        assert result is not None, "New pattern should NOT be excluded by noise floor"
        assert abs(result - 0.70) < 0.05, f"Expected ~0.70, got {result}"

    def test_floor_protection(self, monkeypatch):
        """succ=0, fail=3 -> eff = 7/13 ~= 0.538 > CONF_FLOOR -> uses eff."""
        mfh = _load_mfh(monkeypatch)
        # Beta posterior: (7+0) / (7+3+0+3) = 7/13 ~= 0.538
        # 0.538 > MIN_SURFACE_CONF(0.15) and > CONF_FLOOR(0.30) -> multiply by eff
        payload = {"succ": 0.0, "fail": 3.0, "last_decay_at": _T0}
        result = mfh._pattern_score_gate(payload, 1.0)
        assert result is not None
        assert abs(result - 7.0 / 13.0) < 0.05, f"Expected ~{7 / 13:.3f}, got {result}"


# ---------------------------------------------------------------------------
# Tests for _search_learned_patterns
# ---------------------------------------------------------------------------


class TestSearchLearnedPatterns:
    def test_overlap_hit_tagged(self, monkeypatch):
        """Matching tokens -> result tagged _collection='learned_patterns'."""
        mfh = _load_mfh(monkeypatch)

        fake_client = _make_qdrant_stub(
            [
                _FakePoint(
                    {
                        "content": "alpha beta gamma",
                        "category": "pattern",
                        "succ": 5.0,
                        "fail": 0.0,
                        "last_decay_at": _T0,
                    },
                    id="p1",
                )
            ]
        )
        import qdrant_client as _qc

        monkeypatch.setattr(_qc, "QdrantClient", fake_client)
        monkeypatch.setitem(sys.modules, "qdrant_client", _qc)

        query_tokens = set(mfh.tokenize("alpha beta"))
        import time

        results = mfh._search_learned_patterns(query_tokens, time.monotonic(), limit=10)

        assert len(results) == 1
        assert results[0]["_collection"] == "learned_patterns"
        assert results[0]["id"] == "p1"
        assert results[0]["score"] >= mfh.SCORE_THRESHOLD

    def test_non_overlapping_returns_empty(self, monkeypatch):
        """No token overlap -> empty list."""
        mfh = _load_mfh(monkeypatch)

        fake_client = _make_qdrant_stub(
            [
                _FakePoint(
                    {
                        "content": "completely unrelated xyz",
                        "category": "pattern",
                        "succ": 5.0,
                        "fail": 0.0,
                        "last_decay_at": _T0,
                    },
                    id="p2",
                )
            ]
        )
        import qdrant_client as _qc

        monkeypatch.setattr(_qc, "QdrantClient", fake_client)

        query_tokens = set(mfh.tokenize("alpha beta"))
        import time

        results = mfh._search_learned_patterns(query_tokens, time.monotonic(), limit=10)

        assert results == []

    def test_qdrant_raises_fail_soft(self, monkeypatch):
        """QdrantClient raising any exception -> fail-soft, returns []."""
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

    def test_archived_excluded_from_fallback(self, monkeypatch):
        """Archived pattern (expired_at set) excluded by gate even in fallback path."""
        mfh = _load_mfh(monkeypatch)

        fake_client = _make_qdrant_stub(
            [
                _FakePoint(
                    {
                        "content": "alpha beta archived",
                        "category": "pattern",
                        "succ": 5.0,
                        "fail": 0.0,
                        "last_decay_at": _T0,
                        "expired_at": _T0,
                    },
                    id="p3",
                )
            ]
        )
        import qdrant_client as _qc

        monkeypatch.setattr(_qc, "QdrantClient", fake_client)

        query_tokens = set(mfh.tokenize("alpha beta"))
        import time

        results = mfh._search_learned_patterns(query_tokens, time.monotonic(), limit=10)

        assert results == [], "Archived pattern must be excluded by gate in fallback path"


# ---------------------------------------------------------------------------
# REGRESSION GUARD -- section 24: learned_patterns via SEMANTIC path
# ---------------------------------------------------------------------------


class TestSearchQdrantLearnedPatternsSemantic:
    """Section 24 P0: learned_patterns surface via the SEMANTIC loop (TEI healthy).
    The old always-on token-overlap path is now TEI-DOWN FALLBACK only."""

    def test_learned_patterns_present_when_semantic_hits(self, monkeypatch):
        """TEI healthy: learned_patterns hit surfaces via semantic loop, gated, tagged."""
        mfh = _load_mfh(monkeypatch)

        semantic_mod = types.ModuleType("shared.semantic_search")

        def _fake_embed(text, timeout=1.5):
            return [0.1] * 10  # truthy non-empty vector

        def _fake_search(collection, embedding, limit=5, timeout=1.0):
            if collection == "learned_patterns":
                return [
                    {
                        "id": "lp1",
                        "score": 0.75,
                        "payload": {
                            "content": "alpha beta pattern",
                            "category": "pattern",
                            "succ": 5.0,
                            "fail": 0.0,
                            "last_decay_at": _T0,
                        },
                    }
                ]
            # skill_library / others return a generic semantic hit
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

        shared_pkg = sys.modules.get("shared") or types.ModuleType("shared")
        monkeypatch.setitem(sys.modules, "shared", shared_pkg)
        monkeypatch.setitem(sys.modules, "shared.semantic_search", semantic_mod)

        # QdrantClient.scroll must NOT be called when TEI is up (fallback disabled)
        class _UnexpectedScrollClient:
            def __init__(self, **kwargs):
                pass

            def scroll(self, **kwargs):
                raise AssertionError("QdrantClient.scroll should not be called when TEI is up")

        import qdrant_client as _qc

        monkeypatch.setattr(_qc, "QdrantClient", _UnexpectedScrollClient)

        query_tokens = set(mfh.tokenize("alpha beta"))
        results = mfh.search_qdrant(query_tokens, limit=10, prompt="alpha beta")

        ids = [r.get("id") for r in results]
        collections = [r.get("_collection") for r in results]

        assert "sem1" in ids, f"Semantic result missing from {ids}"
        assert "lp1" in ids, (
            f"learned_patterns entry 'lp1' missing -- semantic surfacing failed. ids={ids}"
        )
        assert "learned_patterns" in collections, (
            f"No _collection='learned_patterns' in results. collections={collections}"
        )

    def test_archived_pattern_excluded_from_semantic_path(self, monkeypatch):
        """TEI healthy: archived learned_patterns hit is gated out."""
        mfh = _load_mfh(monkeypatch)

        semantic_mod = types.ModuleType("shared.semantic_search")

        def _fake_embed(text, timeout=1.5):
            return [0.1] * 10

        def _fake_search(collection, embedding, limit=5, timeout=1.0):
            if collection == "learned_patterns":
                return [
                    {
                        "id": "lp_archived",
                        "score": 0.75,
                        "payload": {
                            "content": "archived pattern",
                            "category": "pattern",
                            "succ": 5.0,
                            "fail": 0.0,
                            "last_decay_at": _T0,
                            "expired_at": _T0,
                        },
                    }
                ]
            return []

        semantic_mod.embed_query_tei = _fake_embed
        semantic_mod.search_qdrant_semantic = _fake_search

        shared_pkg = sys.modules.get("shared") or types.ModuleType("shared")
        monkeypatch.setitem(sys.modules, "shared", shared_pkg)
        monkeypatch.setitem(sys.modules, "shared.semantic_search", semantic_mod)

        query_tokens = set(mfh.tokenize("archived pattern"))
        results = mfh.search_qdrant(query_tokens, limit=10, prompt="archived pattern")

        ids = [r.get("id") for r in results]
        assert "lp_archived" not in ids, f"Archived pattern should be excluded. ids={ids}"

    def test_tei_down_fallback_uses_token_overlap(self, monkeypatch):
        """TEI down (embed returns []): fallback token-overlap runs for learned_patterns."""
        mfh = _load_mfh(monkeypatch)

        semantic_mod = types.ModuleType("shared.semantic_search")

        def _fake_embed_empty(text, timeout=1.5):
            return []  # TEI down

        semantic_mod.embed_query_tei = _fake_embed_empty
        semantic_mod.search_qdrant_semantic = lambda *a, **kw: []

        shared_pkg = sys.modules.get("shared") or types.ModuleType("shared")
        monkeypatch.setitem(sys.modules, "shared", shared_pkg)
        monkeypatch.setitem(sys.modules, "shared.semantic_search", semantic_mod)

        # QdrantClient.scroll IS expected (fallback active)
        fake_client = _make_qdrant_stub(
            [
                _FakePoint(
                    {
                        "content": "alpha beta pattern",
                        "category": "pattern",
                        "succ": 5.0,
                        "fail": 0.0,
                        "last_decay_at": _T0,
                    },
                    id="lp_fallback",
                )
            ]
        )
        import qdrant_client as _qc

        monkeypatch.setattr(_qc, "QdrantClient", fake_client)

        query_tokens = set(mfh.tokenize("alpha beta"))
        results = mfh.search_qdrant(query_tokens, limit=10, prompt="alpha beta")

        ids = [r.get("id") for r in results]
        collections = [r.get("_collection") for r in results]

        assert "lp_fallback" in ids, (
            f"TEI-down fallback did not surface learned_patterns. ids={ids}"
        )
        assert "learned_patterns" in collections


# ---------------------------------------------------------------------------
# §24 P1 — hybrid RRF (always-on lexical arm, RRF boost, TEI-down lexical-only)
# ---------------------------------------------------------------------------


def _stub_semantic(monkeypatch, embed_ret, search_fn):
    """Install a fake shared.semantic_search with given embed return + search fn."""
    semantic_mod = types.ModuleType("shared.semantic_search")
    semantic_mod.embed_query_tei = lambda text, timeout=1.5: embed_ret
    semantic_mod.search_qdrant_semantic = search_fn
    shared_pkg = sys.modules.get("shared") or types.ModuleType("shared")
    monkeypatch.setitem(sys.modules, "shared", shared_pkg)
    monkeypatch.setitem(sys.modules, "shared.semantic_search", semantic_mod)


class TestSection24P1HybridRRF:
    def test_lexical_arm_always_on_when_tei_up(self, monkeypatch):
        """§24 P1: token-overlap (_search_learned_patterns) runs even when TEI healthy."""
        mfh = _load_mfh(monkeypatch)
        calls = {"n": 0}

        def _spy(query_tokens, start, limit):
            calls["n"] += 1
            return [
                {
                    "source": "qdrant",
                    "id": "lex1",
                    "content": "alpha beta lexical",
                    "category": "pattern",
                    "score": 0.9,
                    "_collection": "learned_patterns",
                }
            ]

        monkeypatch.setattr(mfh, "_search_learned_patterns", _spy)
        _stub_semantic(
            monkeypatch,
            [0.1] * 10,
            lambda c, e, limit=5, timeout=1.0: (
                [{"id": "sk1", "score": 0.8, "payload": {"skill_name": "s", "description": "d"}}]
                if c == "skill_library"
                else []
            ),
        )
        out = mfh.search_qdrant(set(mfh.tokenize("alpha beta")), limit=10, prompt="alpha beta")
        assert calls["n"] == 1, "lexical arm must ALWAYS run (not fallback-only) in P1"
        assert all("fused_score" in r for r in out), "RRF must produce fused_score"
        assert any(r["id"] == "lex1" for r in out)

    def test_rrf_boost_when_in_both_arms(self, monkeypatch):
        """Pattern present in BOTH dense + lexical (same content) → fused > single-arm."""
        mfh = _load_mfh(monkeypatch)
        SHARED = "alpha beta gamma shared pattern"

        def _search(collection, embedding, limit=5, timeout=1.0):
            if collection == "learned_patterns":
                return [
                    {
                        "id": "both",
                        "score": 0.7,
                        "payload": {
                            "content": SHARED,
                            "category": "pattern",
                            "succ": 5.0,
                            "fail": 0.0,
                            "last_decay_at": _T0,
                        },
                    }
                ]
            return []

        def _lex(query_tokens, start, limit):
            return [
                {
                    "source": "qdrant",
                    "id": "both",
                    "content": SHARED[:200],
                    "category": "pattern",
                    "score": 0.9,
                    "_collection": "learned_patterns",
                },
                {
                    "source": "qdrant",
                    "id": "lexonly",
                    "content": "delta epsilon only",
                    "category": "pattern",
                    "score": 0.9,
                    "_collection": "learned_patterns",
                },
            ]

        monkeypatch.setattr(mfh, "_search_learned_patterns", _lex)
        _stub_semantic(monkeypatch, [0.1] * 10, _search)
        out = mfh.search_qdrant(set(mfh.tokenize("alpha beta gamma")), limit=10, prompt="x")
        by_content = {r["content"][:30]: r["fused_score"] for r in out}
        both = next(r for r in out if r["content"].startswith("alpha beta gamma"))
        lexonly = next(r for r in out if r["content"].startswith("delta epsilon"))
        # 'both' in dense(0.3)+lexical(0.7) arms; 'lexonly' only lexical(0.7) → both ranks higher
        assert both["fused_score"] > lexonly["fused_score"]

    def test_tei_down_lexical_only(self, monkeypatch):
        """TEI down (embed→None) → only lexical arm → still surfaces (no crash)."""
        mfh = _load_mfh(monkeypatch)
        monkeypatch.setattr(
            mfh,
            "_search_learned_patterns",
            lambda q, s, l: [
                {
                    "source": "qdrant",
                    "id": "lexA",
                    "content": "alpha beta",
                    "category": "pattern",
                    "score": 0.8,
                    "_collection": "learned_patterns",
                }
            ],
        )
        _stub_semantic(monkeypatch, None, lambda *a, **k: [])  # TEI down
        out = mfh.search_qdrant(set(mfh.tokenize("alpha beta")), limit=10, prompt="alpha beta")
        assert any(r["id"] == "lexA" for r in out)
        assert all("fused_score" in r for r in out)
