"""Unit tests for §БП G4 end-to-end memory benchmark (pure logic, no live deps).

The live seed/recall path needs TEI + Qdrant; here we test the pure evaluation
core (dataset load, per-query scoring, aggregation) with a stub harness and
precomputed ranked-hash lists — so a regression in the metric wiring is caught
in CI without infra.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "memory_e2e_benchmark", str(_ROOT / "scripts" / "memory_e2e_benchmark.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()
H = MOD._load_harness()  # real metric functions (pure, no infra)


def test_load_dataset_shape():
    rows = MOD.load_dataset()
    assert len(rows) >= 8
    for r in rows:
        assert {"id", "fact", "query"} <= set(r)


def test_perfect_recall_rank1():
    # target hash sits at rank 1 -> hit/recall/mrr/ndcg all 1.0
    target = H.content_hash("some fact text")
    metrics = MOD.score_query([target, "other", "noise"], target, k=5, harness=H)
    assert metrics["hit"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["ndcg"] == 1.0
    assert metrics["rank"] == 1


def test_miss_scores_zero():
    target = H.content_hash("the relevant fact")
    metrics = MOD.score_query(["a", "b", "c"], target, k=5, harness=H)
    assert metrics["hit"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["mrr"] == 0.0
    assert metrics["rank"] == 0


def test_rank2_mrr_half():
    target = H.content_hash("fact")
    metrics = MOD.score_query(["x", target], target, k=5, harness=H)
    assert metrics["hit"] == 1.0
    assert metrics["mrr"] == 0.5
    assert metrics["rank"] == 2


def test_hit_beyond_k_is_miss():
    # target at position 6 with k=5 -> hit@5 == 0 (discrimination check)
    target = H.content_hash("late fact")
    ranked = ["a", "b", "c", "d", "e", target]
    metrics = MOD.score_query(ranked, target, k=5, harness=H)
    assert metrics["hit"] == 0.0
    assert metrics["rank"] == 6  # rank is absolute; hit@k respects k


def test_evaluate_offline_aggregates():
    rows = [
        {"id": "q1", "fact": "alpha fact", "query": "?"},
        {"id": "q2", "fact": "beta fact", "query": "?"},
        {"id": "q3", "fact": "gamma fact", "query": "?"},
    ]
    ha, hb = H.content_hash("alpha fact"), H.content_hash("beta fact")
    ranked_by_id = {
        "q1": [ha],  # hit rank1
        "q2": ["noise", hb],  # hit rank2
        "q3": ["noise"],  # miss
    }
    out = MOD.evaluate_offline(rows, ranked_by_id, k=5, harness=H)
    agg = out["aggregate"]
    assert agg["n"] == 3
    assert agg["hit_rate"] == round(2 / 3, 4)
    assert agg["misses"] == ["q3"]
    # mrr = (1 + 0.5 + 0) / 3
    assert agg["mrr"] == round(1.5 / 3, 4)


def test_aggregate_empty_safe():
    agg = MOD.aggregate([])
    assert agg["n"] == 0
    assert agg["hit_rate"] == 0.0
    assert agg["misses"] == []


def test_missing_query_id_is_miss():
    # a query id absent from ranked_by_id -> empty ranked list -> miss (not a crash)
    rows = [{"id": "qX", "fact": "orphan fact", "query": "?"}]
    out = MOD.evaluate_offline(rows, {}, k=5, harness=H)
    assert out["aggregate"]["hit_rate"] == 0.0
    assert out["aggregate"]["misses"] == ["qX"]
