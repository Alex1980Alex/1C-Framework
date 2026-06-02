"""Smoke tests for section 25 B0 memory golden-set harness (service-independent).

Exercises the pure replay + metric functions on synthetic captured candidates.
No TEI / Qdrant. A drift-guard test compares the harness rrf_merge against the
hook's verbatim copy when the hook module is importable (else skipped).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _ROOT / "scripts" / "memory_golden_harness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("memory_golden_harness", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load_module()


def test_content_hash_stable():
    assert H.content_hash("alpha") == H.content_hash("alpha")
    assert H.content_hash("alpha") != H.content_hash("beta")
    assert len(H.content_hash("x")) == 16


def test_rrf_merge_orders_and_dedups():
    # Same content in two arms fuses (sums rrf), and a higher-weighted arm wins.
    arms = {
        "skill": [{"content": "A"}, {"content": "B"}],
        "pattern_lexical": [{"content": "A"}, {"content": "C"}],
    }
    weights = {"skill": 0.5, "pattern_lexical": 0.7}
    merged = H.rrf_merge(arms, weights, k=60)
    contents = [m["content"] for m in merged]
    assert contents[0] == "A"  # appears in both arms -> highest fused score
    assert set(contents) == {"A", "B", "C"}  # dedup, no duplicates
    assert len(merged) == 3


def test_assemble_arms_gating():
    cap = {
        "skill": [{"content": "skill-hit"}],
        "pattern_dense": [
            {"content": "p-keep", "eff_conf": 0.6, "archived": False},
            {"content": "p-lowconf", "eff_conf": 0.05, "archived": False},  # below floor
            {"content": "p-archived", "eff_conf": 0.9, "archived": True},   # archived
        ],
        "pattern_lexical": [
            {"content": "lex-strong", "overlap": 0.8, "eff_conf": 0.6, "archived": False},
            {"content": "lex-weak", "overlap": 0.1, "eff_conf": 0.6, "archived": False},  # < SCORE_THRESHOLD
        ],
    }
    config = dict(H.DEFAULT_CONFIG)
    arms = H.assemble_arms(cap, config)
    dense = [c["content"] for c in arms["pattern_dense"]]
    lex = [c["content"] for c in arms["pattern_lexical"]]
    assert dense == ["p-keep"]  # lowconf + archived dropped
    assert lex == ["lex-strong"]  # weak overlap dropped
    assert [c["content"] for c in arms["skill"]] == ["skill-hit"]


def test_min_surface_conf_threshold_moves_inclusion():
    cap = {"pattern_dense": [{"content": "p", "eff_conf": 0.20, "archived": False}]}
    lenient = dict(H.DEFAULT_CONFIG, min_surface_conf=0.15)
    strict = dict(H.DEFAULT_CONFIG, min_surface_conf=0.30)
    assert len(H.assemble_arms(cap, lenient)["pattern_dense"]) == 1
    assert len(H.assemble_arms(cap, strict)["pattern_dense"]) == 0


def test_surfaced_hashes_end_to_end():
    cap = {
        "skill": [{"content": "the-skill"}],
        "pattern_lexical": [
            {"content": "the-pattern", "overlap": 0.9, "eff_conf": 0.6, "archived": False}
        ],
    }
    ranked = H.surfaced_hashes(cap, dict(H.DEFAULT_CONFIG), k=5)
    assert H.content_hash("the-skill") in ranked
    assert H.content_hash("the-pattern") in ranked


def test_metrics_known_values():
    ranked = ["a", "b", "c", "d"]
    rel = {"a": 2, "c": 1}
    assert H.hit_at_k(ranked, rel, 5) == 1.0
    assert H.hit_at_k(["x", "y"], rel, 5) == 0.0
    assert H.precision_at_k(ranked, rel, 4) == pytest.approx(0.5)
    assert H.precision_at_k(ranked, rel, 0) == 0.0
    assert H.recall_at_k(ranked, rel, 5) == pytest.approx(1.0)
    assert H.recall_at_k(ranked, {}, 5) == 0.0
    assert H.mrr(ranked, rel) == pytest.approx(1.0)  # first item is relevant
    assert H.mrr(["x", "c"], rel) == pytest.approx(0.5)
    # NDCG: perfect order (grade 2 then grade 1) -> 1.0
    assert H.ndcg_at_k(["a", "c"], rel, 5) == pytest.approx(1.0)
    assert H.ndcg_at_k(["x", "y"], rel, 5) == 0.0


def test_evaluate_config_aggregates():
    golden = [
        {"id": "q1", "kind": "skill", "relevant": [{"hash": H.content_hash("good"), "grade": 2}]},
        {"id": "q2", "kind": "pattern", "relevant": [{"hash": H.content_hash("nope"), "grade": 2}]},
    ]
    captures = {
        "q1": {"skill": [{"content": "good"}]},
        "q2": {"skill": [{"content": "other"}]},
    }
    rep = H.evaluate_config(golden, captures, dict(H.DEFAULT_CONFIG), k=5)
    assert rep["n_queries"] == 2
    assert rep["hit_rate"] == pytest.approx(0.5)  # q1 hits, q2 misses


def test_load_tuning_config_defaults(tmp_path):
    # missing file -> defaults
    cfg = H.load_tuning_config(tmp_path / "nope.json")
    assert cfg["min_surface_conf"] == H.DEFAULT_CONFIG["min_surface_conf"]
    assert cfg["surface_rrf_weights"]["pattern_lexical"] == 0.7


def test_load_golden_split_filter(tmp_path):
    p = tmp_path / "g.jsonl"
    p.write_text(
        '{"id": "a", "query": "x", "relevant": [], "split": "train"}\n'
        '{"id": "b", "query": "y", "relevant": [], "split": "heldout"}\n'
        "garbage line\n",
        encoding="utf-8",
    )
    assert [r["id"] for r in H.load_golden(p)] == ["a", "b"]
    assert [r["id"] for r in H.load_golden(p, split="heldout")] == ["b"]


def test_rrf_merge_matches_hook_contract():
    """Drift guard: harness rrf_merge must equal the hook's verbatim copy."""
    hook_path = _ROOT / ".claude" / "hooks" / "memory-first-hook.py"
    if not hook_path.exists():
        pytest.skip("hook module not present")
    spec = importlib.util.spec_from_file_location("mfh_drift", hook_path)
    assert spec and spec.loader
    try:
        mfh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mfh)
    except Exception:
        pytest.skip("hook module not importable")
    arms = {
        "skill": [{"content": "A"}, {"content": "B"}],
        "pattern_dense": [{"content": "B"}, {"content": "C"}],
        "pattern_lexical": [{"content": "A"}, {"content": "D"}],
    }
    weights = H.DEFAULT_CONFIG["surface_rrf_weights"]
    mine = [m["content"] for m in H.rrf_merge(arms, weights, k=60)]
    theirs = [m["content"] for m in mfh.rrf_merge(arms, weights, k=60)]
    assert mine == theirs
