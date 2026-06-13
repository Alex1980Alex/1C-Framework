"""Regression tests for the GT lint (roadmap 260613 A8/A10).

Pins the leakage invariant: a `transcript-router` (router-derived) label must
never land in train/test — that is the F1 contamination the follow-up removes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _load_lint():
    spec = importlib.util.spec_from_file_location(
        "lint_skill_router_gt", _ROOT / "scripts" / "lint_skill_router_gt.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lint = _load_lint()
CATALOG = {"bsl-development", "qdrant-operations", "code-verify"}


def _row(**kw):
    base = {
        "prompt": "p",
        "expected_skills": ["bsl-development"],
        "expected_bundles": ["research-1c"],
        "intent": "action",
        "source": "spec",
        "split": "train",
    }
    base.update(kw)
    return base


def test_clean_rows_pass():
    rows = [_row(), _row(split="test"), _row(intent="informational", expected_skills=[], expected_bundles=[])]
    assert lint.lint_rows(rows, CATALOG) == []


def test_leakage_in_train_is_flagged():
    rows = [_row(source="transcript-router", split="train")]
    issues = lint.lint_rows(rows, CATALOG)
    assert any("LEAKAGE" in it for it in issues)


def test_leakage_in_test_is_flagged():
    rows = [_row(source="transcript-router", split="test")]
    assert any("LEAKAGE" in it for it in lint.lint_rows(rows, CATALOG))


def test_transcript_router_in_quarantine_is_ok():
    rows = [_row(source="transcript-router", split="quarantine")]
    assert lint.lint_rows(rows, CATALOG) == []


def test_unknown_skill_flagged():
    rows = [_row(expected_skills=["no-such-skill"])]
    assert any("unknown skill" in it for it in lint.lint_rows(rows, CATALOG))


def test_informational_with_skills_flagged():
    rows = [_row(intent="informational", expected_skills=["bsl-development"])]
    assert any("expected_skills nonempty" in it for it in lint.lint_rows(rows, CATALOG))


def test_missing_field_flagged():
    bad = _row()
    del bad["source"]
    assert any("missing fields" in it for it in lint.lint_rows([bad], CATALOG))


def test_invalid_split_flagged():
    rows = [_row(split="holdout")]
    assert any("invalid split" in it for it in lint.lint_rows(rows, CATALOG))


def test_coverage_warns_on_tiny_test():
    rows = [_row(split="test")]  # 1 action, 0 silence, 1 domain
    warns = lint.coverage_warnings(rows)
    assert any("silence" in w for w in warns)
    assert any("domains" in w for w in warns)
