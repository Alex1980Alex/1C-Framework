"""Unit tests for the train-only A2-weight optimizer (roadmap 260613 B5).

Covers the pure helpers (set_coord / select_best / is_overfit). The eval-subprocess
path (run_eval) is integration-only — not exercised here (no router/Qdrant in unit).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "tune_skill_router", _ROOT / "scripts" / "tune_skill_router.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tune = _load()
BASE = {
    "bsl_signal_weights": {"bsl-dev": 3, "research-1c": 1},
    "conn_str_weights": {"research-1c": 3},
    "literal_name_weight": 4,
    "literal_name_min_len": 6,
}


def test_set_coord_literal():
    out = tune.set_coord(BASE, "literal", 6)
    assert out["literal_name_weight"] == 6
    assert BASE["literal_name_weight"] == 4  # original untouched (deep copy)


def test_set_coord_bsl_and_conn():
    assert tune.set_coord(BASE, "bsl", 5)["bsl_signal_weights"]["bsl-dev"] == 5
    assert tune.set_coord(BASE, "conn", 2)["conn_str_weights"]["research-1c"] == 2
    # other keys preserved
    assert tune.set_coord(BASE, "bsl", 5)["bsl_signal_weights"]["research-1c"] == 1


def test_set_coord_unknown_raises():
    with pytest.raises(ValueError):
        tune.set_coord(BASE, "nonsense", 1)


def test_select_best_picks_max_f1():
    cands = [
        {"a2": BASE, "train_f1": 0.70, "silence": 0.8},
        {"a2": tune.set_coord(BASE, "literal", 5), "train_f1": 0.74, "silence": 0.8},
        {"a2": tune.set_coord(BASE, "literal", 6), "train_f1": 0.72, "silence": 0.8},
    ]
    assert tune.select_best(cands)["train_f1"] == 0.74


def test_select_best_tiebreak_smaller_weight():
    # equal f1 → prefer smaller total weight (Occam, avoid inflating weights)
    light = tune.set_coord(BASE, "literal", 3)  # total = 3+3+3 = 9
    heavy = tune.set_coord(BASE, "literal", 6)  # total = 6+3+3 = 12
    cands = [
        {"a2": heavy, "train_f1": 0.74, "silence": 0.8},
        {"a2": light, "train_f1": 0.74, "silence": 0.8},
    ]
    assert tune.select_best(cands)["a2"] is light


def test_select_best_none_f1_sorts_last():
    cands = [
        {"a2": BASE, "train_f1": None, "silence": 0.9},
        {"a2": tune.set_coord(BASE, "literal", 5), "train_f1": 0.60, "silence": 0.5},
    ]
    assert tune.select_best(cands)["train_f1"] == 0.60


def test_is_overfit():
    assert tune.is_overfit(0.85, 0.70, 0.10) is True  # gap 0.15 > 0.10
    assert tune.is_overfit(0.80, 0.74, 0.10) is False  # gap 0.06
    assert tune.is_overfit(None, 0.70) is False
    assert tune.is_overfit(0.80, None) is False
