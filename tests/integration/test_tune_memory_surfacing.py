"""Smoke tests for section 25 B1/B2 surfacing self-tuning (service-independent).

Covers the offline sweep ranking, the objective, clamp + no-regression gate logic,
and the apply -> rollback file round-trip with a forced gate-pass on synthetic data.
No TEI / Qdrant.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _ROOT / "scripts" / "tune_memory_surfacing.py"


def _load():
    spec = importlib.util.spec_from_file_location("tune_memory_surfacing", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = _load()
H = T.H  # harness module reused by the tuner


def _hash(s: str) -> str:
    return H.content_hash(s)


def test_target_score_composite():
    report = {"ndcg_at_k": 0.8, "hit_rate": 0.6}
    assert T.target_score(report, alpha=0.5) == pytest.approx(0.7)
    assert T.target_score(report, alpha=1.0) == pytest.approx(0.8)
    assert T.target_score(report, alpha=0.0) == pytest.approx(0.6)


def test_build_grid_size_and_shape():
    grid = T.build_grid(H.DEFAULT_CONFIG["surface_rrf_weights"])
    expected = (
        len(T.GRID["skill"]) * len(T.GRID["pattern_dense"]) * len(T.GRID["pattern_lexical"])
        * len(T.GRID["min_surface_conf"]) * len(T.GRID["conf_floor"]) * len(T.GRID["rrf_k"])
    )
    assert len(grid) == expected
    cfg = grid[0]
    assert set(cfg) == {"surface_rrf_weights", "min_surface_conf", "conf_floor", "rrf_k"}
    # experience/conversation arms preserved from base (held fixed).
    assert cfg["surface_rrf_weights"]["experience"] == 0.5


def test_clamp_config_bounds():
    ranges = {"rrf_weight": [0.1, 1.0], "min_surface_conf": [0.05, 0.40], "conf_floor": [0.10, 0.50]}
    cfg = {
        "surface_rrf_weights": {"skill": 5.0, "pattern_dense": 0.3},
        "min_surface_conf": 0.99,
        "conf_floor": 0.30,
        "rrf_k": 60,
    }
    out = T.clamp_config(cfg, ranges)
    assert out["surface_rrf_weights"]["skill"] == 1.0   # clamped down
    assert out["min_surface_conf"] == 0.40              # clamped down


def test_no_regression_guard():
    cur = {"hit_rate": 0.80, "ndcg_at_k": 0.70}
    better = {"hit_rate": 0.82, "ndcg_at_k": 0.72}
    worse = {"hit_rate": 0.70, "ndcg_at_k": 0.70}
    assert T._no_regression(better, cur) is True
    assert T._no_regression(worse, cur) is False
    # within epsilon -> still ok
    tiny_dip = {"hit_rate": 0.795, "ndcg_at_k": 0.70}
    assert T._no_regression(tiny_dip, cur) is True


def test_sweep_ranks_best_first():
    # One pattern target. A config weighting pattern_lexical should rank the target top.
    golden = [
        {"id": "q1", "kind": "pattern",
         "relevant": [{"hash": _hash("the target pattern"), "grade": 2}]},
    ]
    captures = {
        "q1": {
            "pattern_lexical": [
                {"content": "the target pattern", "overlap": 0.9, "eff_conf": 0.6, "archived": False}
            ],
        }
    }
    ranked = T.sweep(golden, captures, k=5, alpha=0.5)
    assert ranked[0]["score"] >= ranked[-1]["score"]
    assert ranked[0]["metrics"]["hit_rate"] == 1.0


def test_promote_apply_then_rollback(tmp_path, monkeypatch):
    """Forced gate-pass: apply writes tuning.json + snapshot; rollback restores it."""
    tuning = tmp_path / "surfacing_tuning.json"
    prev = tmp_path / "surfacing_tuning.prev.json"
    sweep_result = tmp_path / "sweep_result.json"
    monkeypatch.setattr(T, "TUNING_FILE", tuning)
    monkeypatch.setattr(T, "PREV_FILE", prev)
    monkeypatch.setattr(T, "SWEEP_RESULT", sweep_result)
    monkeypatch.setenv("CONFIDENCE_LOG_DISABLE", "1")  # no audit side effects in test

    # Seed an initial (baseline) tuning.json == defaults.
    base_cfg = {
        "surface_rrf_weights": dict(H.DEFAULT_CONFIG["surface_rrf_weights"]),
        "min_surface_conf": 0.15, "conf_floor": 0.30, "rrf_k": 60,
    }
    T.write_tuning(base_cfg, note="baseline")
    assert tuning.exists()
    v_before = __import__("json").loads(tuning.read_text(encoding="utf-8"))["version"]

    # A clearly-better candidate (heavier lexical weight surfaces the target).
    best_cfg = {
        "surface_rrf_weights": dict(H.DEFAULT_CONFIG["surface_rrf_weights"], pattern_lexical=0.9),
        "min_surface_conf": 0.15, "conf_floor": 0.30, "rrf_k": 60,
    }
    sweep_result.write_text(
        __import__("json").dumps({"best": {"config": best_cfg}}), encoding="utf-8"
    )

    # Golden where current config misses but the candidate hits (forces gate PASS).
    golden = [{"id": "q1", "kind": "pattern",
               "relevant": [{"hash": _hash("answer"), "grade": 2}]}]
    captures = {"q1": {
        # current (default) lexical weight 0.7 vs candidate 0.9 -> with a single arm both
        # surface the answer; ensure hit so improvement is non-negative & no regression.
        "pattern_lexical": [{"content": "answer", "overlap": 0.9, "eff_conf": 0.6, "archived": False}],
    }}
    monkeypatch.setattr(H, "load_golden", lambda split=None: golden)
    monkeypatch.setattr(H, "load_captures", lambda *a, **k: captures)

    # Force a gate pass by lowering the improvement threshold to <= 0 and stubbing current
    # to score lower than best.
    args = argparse.Namespace(eval_split="heldout", k=5, alpha=0.5, min_improvement=-1.0, apply=True)
    rc = T.cmd_promote(args)
    assert rc == 0
    after = __import__("json").loads(tuning.read_text(encoding="utf-8"))
    assert after["version"] == v_before + 1
    assert after["surface_rrf_weights"]["pattern_lexical"] == 0.9
    assert prev.exists()  # snapshot taken

    # Rollback restores the baseline (lexical weight back to 0.7).
    rb_args = argparse.Namespace(apply=True)
    assert T.cmd_rollback(rb_args) == 0
    restored = __import__("json").loads(tuning.read_text(encoding="utf-8"))
    assert restored["surface_rrf_weights"]["pattern_lexical"] == 0.7
    # Snapshot consumed (renamed) so a later unrelated regression can't re-trigger.
    assert not prev.exists()
    assert prev.with_suffix(".json.reverted").exists()
    # A second rollback now has nothing to restore.
    assert T.cmd_rollback(rb_args) == 1
