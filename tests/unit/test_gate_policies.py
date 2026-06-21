"""ADR-034 R3 full composition: политики gate_policies + evaluate_gates."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".claude", "hooks"))
from shared.gate_policies import onec_completion_policy, pipeline_policy
from shared.gate_policy import evaluate_gates

pytestmark = pytest.mark.unit


def test_both_fail_one_verdict():
    ctx = {
        "sid": "s",
        "had_edits": True,
        "pipeline_used": False,
        "is_1c": True,
        "recall": False,
        "capture": False,
        "research": False,
    }
    v = evaluate_gates(ctx, [pipeline_policy, onec_completion_policy])
    assert v["allow"] is False
    assert set(v["denied_by"]) == {"pipeline-protocol", "onec-task-completion"}


def test_clean_question_allows():
    v = evaluate_gates(
        {"sid": "s", "had_edits": False, "pipeline_used": True, "is_1c": False},
        [pipeline_policy, onec_completion_policy],
    )
    assert v["allow"] is True


def test_pipeline_used_and_loops_closed_allows():
    ctx = {
        "sid": "s",
        "had_edits": True,
        "pipeline_used": True,
        "is_1c": True,
        "recall": True,
        "capture": True,
        "research": True,
    }
    assert evaluate_gates(ctx, [pipeline_policy, onec_completion_policy])["allow"] is True


def test_pipeline_optout(monkeypatch):
    monkeypatch.setenv("PIPELINE_PROTOCOL_DISABLE", "1")
    assert pipeline_policy({"sid": "s", "had_edits": True, "pipeline_used": False})["allow"] is True


def test_onec_optout(monkeypatch):
    monkeypatch.setenv("ONEC_TASK_GATE_DISABLE", "1")
    ctx = {"is_1c": True, "recall": False, "capture": False, "research": False}
    assert onec_completion_policy(ctx)["allow"] is True


def test_no_session_pipeline_allows():
    assert pipeline_policy({"sid": "", "had_edits": True, "pipeline_used": False})["allow"] is True
