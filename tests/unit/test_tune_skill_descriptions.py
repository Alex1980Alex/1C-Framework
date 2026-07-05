"""Unit tests for BP G3 description-tuning (pure self_recall logic, no router subprocess)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
_ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "tune_skill_descriptions", str(_ROOT / "scripts" / "tune_skill_descriptions.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


def test_all_keywords_route_back_full_recall():
    sc = MOD.score_bundle(["skill-x"], [["skill-x"], ["skill-x", "other"]])
    assert sc["self_recall"] == 1.0


def test_no_keyword_routes_back_zero_recall():
    sc = MOD.score_bundle(["skill-x"], [["other"], ["another"]])
    assert sc["self_recall"] == 0.0
    assert sc["miss_idx"] == [0, 1]


def test_partial_recall():
    sc = MOD.score_bundle(["skill-x"], [["skill-x"], ["other"], ["skill-x"]])
    assert sc["self_recall"] == round(2 / 3, 4)
    assert sc["miss_idx"] == [1]


def test_empty_safe():
    assert MOD.score_bundle([], [])["self_recall"] == 0.0
    assert MOD.score_bundle(["x"], [])["self_recall"] == 0.0


def test_bundle_keywords_merges_and_limits():
    b = {"keywords": ["a", "b"], "weighted_keywords": {"b": 5, "c": 3}}
    assert MOD.bundle_keywords(b) == ["a", "b", "c"]  # dedup b
    assert MOD.bundle_keywords(b, limit=2) == ["a", "b"]


def test_load_bundles_real_config():
    b = MOD.load_bundles()
    assert len(b) >= 50 and "bsl-dev" in b
