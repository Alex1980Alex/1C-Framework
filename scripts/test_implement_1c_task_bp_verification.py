"""Mock-based tests for /implement-1c-task Stage 5.x Live BP verification protocol.

Reference orchestrator + 5 acceptance tests covering the 8-step protocol described
in `.claude/skills/implement-1c-task/SKILL.md` (v2.7.0) and roadmap
`docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md` section 3.2.3.

The orchestrator is a Python reference for the same flow that a Claude skill
performs via `mcp__1c-debug-hmr__*` MCP tool calls. It accepts an injected
`debug_client` (any object exposing the 8 methods listed below) so tests can
swap in mocks and verify the sequence and assertions.

Run:
    python -m pytest scripts/test_implement_1c_task_bp_verification.py -v
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest


@dataclass
class BPVerificationResult:
    """Outcome of one MODIFIED point's BP-verification."""

    point_id: str
    status: str  # "PASS" | "FAIL" | "SKIP"
    actual_line: int | None = None
    actual_module: str | None = None
    variables: dict[str, Any] | None = None
    fallback_used: str | None = None  # None | "break_on_next" | "force_recycle"
    reason: str | None = None
    call_sequence: list[str] = field(default_factory=list)


def verify_bp_for_point(
    debug_client,
    point_id: str,
    object_id: str,
    expected_line: int,
    expected_module: str,
    module_type: str,
    trigger_fn,
    *,
    max_ping_iterations: int = 3,
    allow_force_recycle: bool = False,
) -> BPVerificationResult:
    """Reference 8-step BP-verification orchestrator.

    Matches the protocol in `implement-1c-task/SKILL.md` Stage 5.x.
    `debug_client` is anything that exposes:
      debug_connect, debug_set_breakpoint, debug_get_breakpoints,
      debug_ping, debug_stack_trace, debug_variables, debug_step,
      debug_break_on_next.
    `trigger_fn` is a no-arg callable simulating step 4 (execute_code / query).
    """
    result = BPVerificationResult(point_id=point_id, status="SKIP")
    seq = result.call_sequence

    # Step 1: connect (idempotent — if already connected, debug_client returns same session)
    try:
        seq.append("debug_connect")
        connect_resp = debug_client.debug_connect()
    except Exception as exc:
        result.status = "SKIP"
        result.reason = f"connect failed: {type(exc).__name__}: {exc}"
        return result

    # Roadmap 260511 §3.1: debug_connect may return a dict with
    # {"status": "error", "reason": "infobase_alias_not_found", "available": [...]}
    # for invalid infobase_alias. Surface as SKIP — without this guard, the
    # orchestrator would proceed to set_breakpoint on an unattached session
    # and silently fail (RC1 from GKSTCPLK-2468 incident).
    if isinstance(connect_resp, dict) and connect_resp.get("status") == "error":
        result.status = "SKIP"
        reason = connect_resp.get("reason", "unknown")
        available = connect_resp.get("available", [])
        result.reason = f"connect error: {reason} (available: {available})"
        return result

    # Step 2: set BP
    seq.append("debug_set_breakpoint")
    debug_client.debug_set_breakpoint(
        object_id=object_id,
        line=expected_line,
        module_type=module_type,
    )

    # Step 3: verify BP in cache
    seq.append("debug_get_breakpoints")
    bps = debug_client.debug_get_breakpoints()
    if not any(bp.get("enabled") and bp.get("lineNo") == expected_line for bp in bps):
        result.status = "FAIL"
        result.reason = "BP not in client cache after set_breakpoint"
        return result

    # Step 4: trigger
    seq.append("trigger")
    trigger_fn()

    # Step 5: ping loop until callStackFormed
    stopped = False
    for _ in range(max_ping_iterations):
        seq.append("debug_ping")
        ping_resp = debug_client.debug_ping()
        if ping_resp.get("last_stopped_target_id"):
            stopped = True
            break

    if not stopped:
        # Fallback (a): break_on_next + retry trigger
        seq.append("debug_break_on_next")
        debug_client.debug_break_on_next()
        seq.append("trigger")
        trigger_fn()
        for _ in range(max_ping_iterations):
            seq.append("debug_ping")
            ping_resp = debug_client.debug_ping()
            if ping_resp.get("last_stopped_target_id"):
                stopped = True
                result.fallback_used = "break_on_next"
                break

    if not stopped:
        # Fallback (b): force_recycle_rphost (only when explicitly allowed — dev only)
        if allow_force_recycle:
            seq.append("debug_connect[force_recycle=True]")
            debug_client.debug_connect(force_recycle_rphost=True)
            seq.append("debug_set_breakpoint")
            debug_client.debug_set_breakpoint(
                object_id=object_id,
                line=expected_line,
                module_type=module_type,
            )
            seq.append("trigger")
            trigger_fn()
            for _ in range(max_ping_iterations):
                seq.append("debug_ping")
                ping_resp = debug_client.debug_ping()
                if ping_resp.get("last_stopped_target_id"):
                    stopped = True
                    result.fallback_used = "force_recycle"
                    break

    if not stopped:
        result.status = "SKIP"
        result.reason = "BP did not fire (3 ping iterations + fallbacks exhausted)"
        return result

    # Step 6: stack_trace + assert lineNo
    seq.append("debug_stack_trace")
    frames = debug_client.debug_stack_trace()
    if not frames:
        result.status = "FAIL"
        result.reason = "empty stack_trace after stop"
        return result
    actual_line = frames[0].get("lineNo")
    actual_module = frames[0].get("moduleName", "")
    result.actual_line = actual_line
    result.actual_module = actual_module

    if actual_line != expected_line:
        result.status = "FAIL"
        result.reason = (
            f"lineNo mismatch: expected {expected_line} in {expected_module}, "
            f"got {actual_line} in {actual_module}"
        )
        # Step 8 still required even on FAIL — release rphost
        seq.append("debug_step[Continue]")
        debug_client.debug_step(action="Continue")
        return result

    # Step 7 (optional): variables snapshot
    seq.append("debug_variables")
    result.variables = debug_client.debug_variables()

    # Step 8: release rphost
    seq.append("debug_step[Continue]")
    debug_client.debug_step(action="Continue")

    result.status = "PASS"
    return result


# ─────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────


def _make_happy_client() -> MagicMock:
    """Mock client that returns success at every step."""
    c = MagicMock()
    c.debug_get_breakpoints.return_value = [
        {"enabled": True, "lineNo": 42, "moduleName": "Doc.ABC"}
    ]
    c.debug_ping.return_value = {"last_stopped_target_id": "tgt-1"}
    c.debug_stack_trace.return_value = [
        {"lineNo": 42, "moduleName": "Doc.ABC.SomeProcedure"}
    ]
    c.debug_variables.return_value = {"Counterparty": "LLC Test"}
    return c


# ─────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────


def test_happy_path_all_8_steps_in_order():
    """Happy path: BP fires immediately, lineNo matches, all 8 steps executed."""
    c = _make_happy_client()
    triggered = []

    result = verify_bp_for_point(
        debug_client=c,
        point_id="P1",
        object_id="uuid-abc",
        expected_line=42,
        expected_module="Doc.ABC",
        module_type="ObjectModule",
        trigger_fn=lambda: triggered.append("fired"),
    )

    assert result.status == "PASS"
    assert result.actual_line == 42
    assert result.fallback_used is None
    assert result.variables == {"Counterparty": "LLC Test"}
    assert triggered == ["fired"]
    # Verify ordering of the 8 conceptual steps
    seq = result.call_sequence
    assert seq[0] == "debug_connect"
    assert seq[1] == "debug_set_breakpoint"
    assert seq[2] == "debug_get_breakpoints"
    assert seq[3] == "trigger"
    assert "debug_ping" in seq[4:6]  # ping after trigger
    assert "debug_stack_trace" in seq
    assert "debug_variables" in seq
    assert seq[-1] == "debug_step[Continue]"


def test_bp_timeout_falls_back_to_break_on_next():
    """Step 5 ping returns no stopped target 3x, then break_on_next path succeeds."""
    c = _make_happy_client()
    # First 3 pings return no stop, then break_on_next path succeeds
    c.debug_ping.side_effect = [
        {"last_stopped_target_id": None},
        {"last_stopped_target_id": None},
        {"last_stopped_target_id": None},
        {"last_stopped_target_id": "tgt-1"},  # after break_on_next + retry
    ]

    result = verify_bp_for_point(
        debug_client=c,
        point_id="P1",
        object_id="uuid-abc",
        expected_line=42,
        expected_module="Doc.ABC",
        module_type="ObjectModule",
        trigger_fn=lambda: None,
    )

    assert result.status == "PASS"
    assert result.fallback_used == "break_on_next"
    assert "debug_break_on_next" in result.call_sequence
    # trigger called twice (initial + after break_on_next)
    assert result.call_sequence.count("trigger") == 2


def test_force_recycle_fallback_when_break_on_next_also_fails():
    """break_on_next path also fails, then force_recycle_rphost=True (Solution A)."""
    c = _make_happy_client()
    # 3 ping no-stop (initial) + 3 ping no-stop (after break_on_next) + 1 stop (after recycle)
    c.debug_ping.side_effect = [
        {"last_stopped_target_id": None}, {"last_stopped_target_id": None}, {"last_stopped_target_id": None},
        {"last_stopped_target_id": None}, {"last_stopped_target_id": None}, {"last_stopped_target_id": None},
        {"last_stopped_target_id": "tgt-recycled"},
    ]

    result = verify_bp_for_point(
        debug_client=c,
        point_id="P1",
        object_id="uuid-abc",
        expected_line=42,
        expected_module="Doc.ABC",
        module_type="ObjectModule",
        trigger_fn=lambda: None,
        allow_force_recycle=True,  # dev-only opt-in
    )

    assert result.status == "PASS"
    assert result.fallback_used == "force_recycle"
    # recycle called debug_connect with force_recycle_rphost=True
    recycle_calls = [
        call for call in c.debug_connect.call_args_list if call.kwargs.get("force_recycle_rphost")
    ]
    assert len(recycle_calls) == 1
    assert "debug_connect[force_recycle=True]" in result.call_sequence


def test_stack_trace_line_mismatch_returns_fail_and_releases_rphost():
    """Stop fires but lineNo != expected → FAIL; rphost still released via Continue."""
    c = _make_happy_client()
    c.debug_stack_trace.return_value = [
        {"lineNo": 99, "moduleName": "Doc.Other"}  # wrong line, wrong module
    ]

    result = verify_bp_for_point(
        debug_client=c,
        point_id="P1",
        object_id="uuid-abc",
        expected_line=42,
        expected_module="Doc.ABC",
        module_type="ObjectModule",
        trigger_fn=lambda: None,
    )

    assert result.status == "FAIL"
    assert result.actual_line == 99
    assert "lineNo mismatch" in (result.reason or "")
    # Critical: Continue must still be called to release the paused rphost
    assert "debug_step[Continue]" in result.call_sequence
    c.debug_step.assert_called_with(action="Continue")


def test_debug_hmr_unavailable_returns_skip_without_block():
    """debug_connect raises (server not registered) → SKIP, pipeline continues without BP."""
    c = MagicMock()
    c.debug_connect.side_effect = RuntimeError("MCP server 1c-debug-hmr not available")

    result = verify_bp_for_point(
        debug_client=c,
        point_id="P1",
        object_id="uuid-abc",
        expected_line=42,
        expected_module="Doc.ABC",
        module_type="ObjectModule",
        trigger_fn=lambda: None,
    )

    assert result.status == "SKIP"
    assert "connect failed" in (result.reason or "")
    # No further MCP calls after connect failure
    c.debug_set_breakpoint.assert_not_called()
    c.debug_step.assert_not_called()


def test_alias_invalid_returns_skip_with_available_list():
    """Roadmap 260511 §3.1 + §5 closure: debug_connect returns
    status=error/reason=infobase_alias_not_found dict for invalid alias.
    Orchestrator must surface SKIP without progressing to set_breakpoint.

    Closes the last unchecked acceptance item in
    docs/roadmap/260511_ROADMAP_1C_DEBUG_HMR_DEFICIENCIES_FROM_GKSTCPLK_2468.md §5.
    """
    c = MagicMock()
    c.debug_connect.return_value = {
        "status": "error",
        "reason": "infobase_alias_not_found",
        "provided": "TestDB",
        "available": ["ИБTransportManagementDevelop", "260507_DEV_ATERLETSKIY_53196"],
        "hint": "Use one of available infobases.",
    }

    result = verify_bp_for_point(
        debug_client=c,
        point_id="P1",
        object_id="uuid-abc",
        expected_line=42,
        expected_module="Doc.ABC",
        module_type="ObjectModule",
        trigger_fn=lambda: None,
    )

    assert result.status == "SKIP"
    assert "infobase_alias_not_found" in (result.reason or "")
    # The available list should be surfaced in the reason so the human sees
    # which infobase names exist in the cluster (debugging aid).
    assert "ИБTransportManagementDevelop" in (result.reason or "")
    # Pipeline must NOT progress past Step 1 — no BP set, no trigger, no step.
    c.debug_set_breakpoint.assert_not_called()
    c.debug_get_breakpoints.assert_not_called()
    c.debug_step.assert_not_called()
    # Only debug_connect should be in the call sequence.
    assert result.call_sequence == ["debug_connect"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
