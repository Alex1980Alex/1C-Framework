"""R3 (ADR-034): тесты composable gate-policy (fail-closed + decision-log)."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".claude", "hooks"))
from shared.gate_policy import decision, evaluate_gates, log_decision

pytestmark = pytest.mark.unit


def _allow(ctx):
    return decision("a", True)


def _deny(ctx):
    return decision("b", False, "nope")


def _boom(ctx):
    raise ValueError("x")


def test_any_deny_blocks():
    r = evaluate_gates({}, [_allow, _deny])
    assert r["allow"] is False
    assert r["denied_by"] == ["b"]


def test_all_allow_passes():
    r = evaluate_gates({}, [_allow, _allow])
    assert r["allow"] is True
    assert r["denied_by"] == []


def test_policy_error_is_deny():
    r = evaluate_gates({}, [_boom])
    assert r["allow"] is False


def test_log_decision_writes(tmp_path):
    p = tmp_path / "gd.jsonl"
    log_decision(decision("g", True, "ok"), log_path=str(p))
    rec = json.loads(p.read_text(encoding="utf-8").strip())
    assert rec["gate"] == "g"
    assert rec["allow"] is True
    assert "ts" in rec
