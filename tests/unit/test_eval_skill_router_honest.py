"""Regression tests for the honest skill-router eval metrics (roadmap 260613 P0).

Locks the F1/F5 fix: the gate must read POOLED `action_f1` (action samples only,
no silence-credit padding), NOT the legacy macro-F1 that scores 1.0 for staying
silent on empty-expected prompts. Also pins the F3 word-boundary semantics for the
literal-skill-name router signal.

The eval script has a hyphen in its filename → loaded via importlib.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _load_eval():
    spec = importlib.util.spec_from_file_location(
        "eval_skill_router", _ROOT / "scripts" / "eval-skill-router.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ev = _load_eval()


def test_split_field_override():
    assert ev._split_of("anything", {"split": "test"}) == "test"
    assert ev._split_of("anything", {"split": "train"}) == "train"


def test_split_hash_is_deterministic_and_valid():
    a = ev._split_of("создай langgraph агента для RAG", {})
    b = ev._split_of("создай langgraph агента для RAG", {})
    assert a == b
    assert a in ("train", "test")


def test_action_f1_excludes_silence_credit():
    # 2 action rows (0.5, 1.0) + 1 silence row scoring f1=1.0 for staying silent.
    # pooled action_f1 = mean(0.5, 1.0) = 0.75 — the silence 1.0 must NOT pad it
    # (legacy macro over all 3 would be (0.5+1.0+1.0)/3 = 0.8333).
    rows = [
        {"is_action": True, "f1": 0.5, "silent_ok": False},
        {"is_action": True, "f1": 1.0, "silent_ok": False},
        {"is_action": False, "f1": 1.0, "silent_ok": True},
    ]
    assert ev._action_f1(rows) == 0.75


def test_action_f1_none_without_action_rows():
    assert ev._action_f1([{"is_action": False, "f1": 1.0, "silent_ok": True}]) is None


def test_silence_accuracy_counts_only_empty_expected():
    rows = [
        {"is_action": True, "f1": 0.0, "silent_ok": False},  # action — ignored here
        {"is_action": False, "f1": 1.0, "silent_ok": True},  # silence, correct
        {"is_action": False, "f1": 0.0, "silent_ok": False},  # silence, wrong
    ]
    assert ev._silence_accuracy(rows) == 0.5


def test_silence_accuracy_none_without_silence_rows():
    assert ev._silence_accuracy([{"is_action": True, "f1": 0.5, "silent_ok": False}]) is None


def _literal_match(skill: str, text: str):
    """Mirror skill-router.py F3 literal-name signal: whole-word, not substring."""
    return re.search(rf"\b{re.escape(skill.lower())}\b", text.lower())


def test_literal_skill_name_is_word_boundary_not_substring():
    # whole-word mention → matches (the legitimate strong signal)
    assert _literal_match("deployment", "нужен deployment кластера")
    assert _literal_match("1c-debug-hmr", "переключись на 1c-debug-hmr сейчас")
    # substring inside an unrelated word/plural → must NOT match (F3 fix)
    assert not _literal_match("deployment", "это redeployment стратегия")
    assert not _literal_match("deployment", "несколько deployments подряд")
    assert not _literal_match("autoresearch", "this is not autoresearchable")
