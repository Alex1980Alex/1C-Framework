"""Mock-based tests for /analyze-1c-task --trace Phase 2.5 Runtime Trace protocol.

Reference orchestrator + 5 acceptance tests covering the 8-step protocol described
in `.claude/skills/analyze-1c-task-v2/SKILL.md` (v4.2.0) and roadmap
`docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md` section 4.

The orchestrator is a Python reference for the same flow that the analyze-1c-task
skill performs via `mcp__1c-debug-hmr__*` MCP tool calls when --trace is active.
It accepts an injected `debug_client` so tests can swap in mocks and verify
sequencing + discrepancy detection.

Run:
    python -m pytest scripts/test_analyze_1c_task_runtime_trace.py -v
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest


@dataclass
class StaticPrediction:
    """What static reading predicted about a runtime branch."""

    condition: str
    predicted_result: str  # "Истина" | "Ложь" | "unknown"
    predicted_branch: str  # "A" | "B" | etc.


@dataclass
class RuntimeBranch:
    """What runtime actually evaluated."""

    condition: str
    runtime_result: str
    taken_branch: str


@dataclass
class RuntimeTraceResult:
    """Outcome of Phase 2.5 Runtime Trace."""

    status: str  # "PASS" | "SKIP" | "FAIL"
    entry_module: str | None = None
    entry_line: int | None = None
    stack: list[dict] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    branches: list[RuntimeBranch] = field(default_factory=list)
    discrepancies: list[str] = field(default_factory=list)
    reason: str | None = None
    call_sequence: list[str] = field(default_factory=list)


def should_trigger_trace(static_branches: list[StaticPrediction], cli_flag: bool) -> bool:
    """Self-decision logic: trigger if --trace flag OR >=3 runtime-dependent branches.

    A branch is runtime-dependent if predicted_result == "unknown".
    """
    if cli_flag:
        return True
    runtime_dependent = sum(1 for b in static_branches if b.predicted_result == "unknown")
    return runtime_dependent >= 3


def run_runtime_trace(
    debug_client,
    entry_module: str,
    entry_line: int,
    object_id: str,
    module_type: str,
    static_predictions: list[StaticPrediction],
    trigger_fn,
    *,
    max_ping_iterations: int = 3,
) -> RuntimeTraceResult:
    """Reference 8-step Runtime Trace orchestrator.

    Matches the protocol in `analyze-1c-task-v2/SKILL.md` Phase 2.5.
    Captures stack + variables + branch evaluation, computes discrepancies
    against `static_predictions`.
    """
    result = RuntimeTraceResult(status="SKIP")
    seq = result.call_sequence
    result.entry_module = entry_module
    result.entry_line = entry_line

    # Step 1: connect
    try:
        seq.append("debug_connect")
        debug_client.debug_connect()
    except Exception as exc:
        result.status = "SKIP"
        result.reason = f"connect failed: {type(exc).__name__}: {exc}"
        return result

    # Step 2: identify entry-point (caller-provided here; in skill this comes from metadata)
    # Step 3: set BP on entry
    seq.append("debug_set_breakpoint")
    debug_client.debug_set_breakpoint(
        object_id=object_id,
        line=entry_line,
        module_type=module_type,
    )

    # Step 4: trigger
    seq.append("trigger")
    trigger_fn()

    # Step 5: ping for callStackFormed
    stopped = False
    for _ in range(max_ping_iterations):
        seq.append("debug_ping")
        ping_resp = debug_client.debug_ping()
        if ping_resp.get("last_stopped_target_id"):
            stopped = True
            break

    if not stopped:
        result.status = "SKIP"
        result.reason = f"BP did not fire after {max_ping_iterations} ping iterations"
        return result

    # Step 6: iterative stack_trace + variables for each frame
    seq.append("debug_stack_trace")
    frames = debug_client.debug_stack_trace()
    result.stack = frames or []

    if not frames:
        # Always release rphost even on early FAIL
        seq.append("debug_step[Continue]")
        debug_client.debug_step(action="Continue")
        result.status = "FAIL"
        result.reason = "empty stack_trace"
        return result

    for frame_idx, _frame in enumerate(frames):
        seq.append(f"debug_variables[stack_level={frame_idx}]")
        frame_vars = debug_client.debug_variables(stack_level=frame_idx)
        if frame_idx == 0:
            result.variables = frame_vars or {}

    # Step 6 (continued): evaluate each branch condition
    for pred in static_predictions:
        seq.append(f"debug_evaluate[{pred.condition}]")
        eval_result = debug_client.debug_evaluate(expression=pred.condition)
        rt_value = eval_result.get("value", "unknown")
        rt_branch = eval_result.get("branch", "?")
        result.branches.append(
            RuntimeBranch(
                condition=pred.condition,
                runtime_result=rt_value,
                taken_branch=rt_branch,
            )
        )

    # Step 7: step through critical branches (in skill this calls debug_step("Step"))
    seq.append("debug_step[Step]")
    debug_client.debug_step(action="Step")

    # Step 8: Continue — release rphost (mandatory)
    seq.append("debug_step[Continue]")
    debug_client.debug_step(action="Continue")

    # Compute discrepancies
    for pred, rt in zip(static_predictions, result.branches):
        if pred.predicted_result == "unknown":
            continue
        if pred.predicted_result != rt.runtime_result:
            result.discrepancies.append(
                f"{entry_module}:{entry_line} cond `{pred.condition}` — "
                f"static predicted {pred.predicted_result} (branch {pred.predicted_branch}), "
                f"runtime returned {rt.runtime_result} (branch {rt.taken_branch})"
            )

    result.status = "PASS"
    if not result.discrepancies:
        result.reason = "No discrepancies — static analysis sufficient"
    return result


def _make_happy_client() -> MagicMock:
    """Mock client that returns success at every step."""
    c = MagicMock()
    c.debug_ping.return_value = {"last_stopped_target_id": "tgt-1"}
    c.debug_stack_trace.return_value = [
        {"level": 0, "moduleName": "Mod.A", "lineNo": 42, "method": "Proc1"},
        {"level": 1, "moduleName": "Mod.B", "lineNo": 100, "method": "Caller"},
    ]
    c.debug_variables.return_value = {"Counterparty": "LLC Alpha", "Amount": 1000}
    return c


def test_happy_path_collects_stack_variables_and_branch_eval():
    """Full happy path: BP fires, stack captured, branches evaluated."""
    c = _make_happy_client()
    c.debug_evaluate.side_effect = [
        {"value": "Истина", "branch": "A"},
        {"value": "Ложь", "branch": "B"},
    ]
    statics = [
        StaticPrediction("Type1Check", "Истина", "A"),
        StaticPrediction("UserCheck", "Ложь", "B"),
    ]

    result = run_runtime_trace(
        debug_client=c,
        entry_module="Mod.A",
        entry_line=42,
        object_id="uuid-x",
        module_type="ObjectModule",
        static_predictions=statics,
        trigger_fn=lambda: None,
    )

    assert result.status == "PASS"
    assert len(result.stack) == 2
    assert result.variables == {"Counterparty": "LLC Alpha", "Amount": 1000}
    assert len(result.branches) == 2
    assert result.branches[0].runtime_result == "Истина"
    assert result.discrepancies == []
    assert result.reason == "No discrepancies — static analysis sufficient"
    assert result.call_sequence[-1] == "debug_step[Continue]"


def test_self_decision_triggers_on_3_runtime_branches():
    """Self-decision: skill self-triggers Phase 2.5 if ≥3 runtime-dependent branches."""
    static_with_3_unknowns = [
        StaticPrediction("CondX", "unknown", "?"),
        StaticPrediction("CondY", "unknown", "?"),
        StaticPrediction("CondZ", "unknown", "?"),
    ]
    assert should_trigger_trace(static_with_3_unknowns, cli_flag=False) is True

    static_with_2_unknowns = [
        StaticPrediction("CondX", "unknown", "?"),
        StaticPrediction("CondKnown", "Истина", "A"),
        StaticPrediction("CondZ", "unknown", "?"),
    ]
    assert should_trigger_trace(static_with_2_unknowns, cli_flag=False) is False
    assert should_trigger_trace(static_with_2_unknowns, cli_flag=True) is True


def test_discrepancies_detected_when_runtime_differs_from_static():
    """Critical case: static predicted A, runtime took B → must surface as discrepancy."""
    c = _make_happy_client()
    c.debug_evaluate.return_value = {"value": "Ложь", "branch": "B"}
    statics = [
        StaticPrediction("UserIsAdmin", "Истина", "A"),
    ]

    result = run_runtime_trace(
        debug_client=c,
        entry_module="Mod.A",
        entry_line=42,
        object_id="uuid-x",
        module_type="ObjectModule",
        static_predictions=statics,
        trigger_fn=lambda: None,
    )

    assert result.status == "PASS"
    assert len(result.discrepancies) == 1
    discrepancy = result.discrepancies[0]
    assert "Mod.A:42" in discrepancy
    assert "static predicted Истина" in discrepancy
    assert "runtime returned Ложь" in discrepancy


def test_bp_timeout_returns_skip_without_block():
    """Step 5 ping returns no stopped target 3x → SKIP with reason."""
    c = _make_happy_client()
    c.debug_ping.return_value = {"last_stopped_target_id": None}

    result = run_runtime_trace(
        debug_client=c,
        entry_module="Mod.A",
        entry_line=42,
        object_id="uuid-x",
        module_type="ObjectModule",
        static_predictions=[],
        trigger_fn=lambda: None,
    )

    assert result.status == "SKIP"
    assert "did not fire" in (result.reason or "")
    c.debug_stack_trace.assert_not_called()


def test_debug_hmr_unavailable_returns_skip_gracefully():
    """debug_connect raises → SKIP, Phase 2.5 quietly skipped, no further calls."""
    c = MagicMock()
    c.debug_connect.side_effect = RuntimeError("1c-debug-hmr not registered")

    result = run_runtime_trace(
        debug_client=c,
        entry_module="Mod.A",
        entry_line=42,
        object_id="uuid-x",
        module_type="ObjectModule",
        static_predictions=[StaticPrediction("CondX", "Истина", "A")],
        trigger_fn=lambda: None,
    )

    assert result.status == "SKIP"
    assert "connect failed" in (result.reason or "")
    c.debug_set_breakpoint.assert_not_called()
    c.debug_stack_trace.assert_not_called()
    c.debug_step.assert_not_called()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
