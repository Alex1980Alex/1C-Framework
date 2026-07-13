"""Unit tests for the shared tool-effectiveness rule-layer (roadmap 260713 P2.2).

Covers `scripts/tool_effectiveness.py` (single-source pair-duration / percentile /
retry-abandonment / step-efficiency / per-server rollup) and the P2.1 gen_ai.*
field aliases in the invocation logger.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


te = _load("_tool_effectiveness", "scripts/tool_effectiveness.py")


# --- pair_durations / percentile ----------------------------------------


def _pre(ts, cid=None):
    return {"event": "PreToolUse", "ts": ts, "tool_call_id": cid}


def _post(ts, cid=None):
    return {"event": "PostToolUse", "ts": ts, "tool_call_id": cid}


def test_pair_durations_join_by_call_id():
    pres = [_pre("2026-07-14T00:00:00", "a"), _pre("2026-07-14T00:00:01", "b")]
    posts = [_post("2026-07-14T00:00:03", "b"), _post("2026-07-14T00:00:05", "a")]
    d = te.pair_durations(pres, posts)
    assert sorted(d) == [2000, 5000]  # b: 1→3s=2000ms, a: 0→5s=5000ms


def test_pair_durations_fifo_without_ids():
    pres = [_pre("2026-07-14T00:00:00")]
    posts = [_post("2026-07-14T00:00:00.100")]
    assert te.pair_durations(pres, posts) == [100]


def test_pair_durations_empty_posts():
    assert te.pair_durations([_pre("2026-07-14T00:00:00")], []) == []


def test_pair_durations_tz_guard_skips_naive_aware_mix():
    # aware Pre vs naive Post → TypeError on subtract → skipped, no crash.
    pres = [_pre("2026-07-14T00:00:00+00:00")]
    posts = [_post("2026-07-14T00:00:01")]
    assert te.pair_durations(pres, posts) == []


def test_percentile():
    assert te.percentile([], 0.5) == 0.0
    assert te.percentile([100], 0.95) == 100.0
    assert te.percentile([0, 100], 0.5) == 50.0


# --- effectiveness_from_posts -------------------------------------------


def test_effectiveness_repeats_and_abandonment():
    posts = [
        {"ts": "1", "args_hash": "x", "outcome": "allow"},
        {"ts": "2", "args_hash": "x", "outcome": "allow"},  # repeat of x
        {"ts": "3", "args_hash": "y", "outcome": "error"},  # last = error → abandon
    ]
    eff = te.effectiveness_from_posts(posts)
    assert eff["repeats"] == 1
    assert eff["abandonment"] is True


def test_effectiveness_recovered_last_ok():
    posts = [
        {"ts": "1", "args_hash": "y", "outcome": "error"},
        {"ts": "2", "args_hash": "y", "outcome": "allow"},  # recovered
    ]
    eff = te.effectiveness_from_posts(posts)
    assert eff["repeats"] == 1  # same args_hash retried
    assert eff["abandonment"] is False


def test_effectiveness_empty():
    eff = te.effectiveness_from_posts([])
    assert eff == {"repeats": 0, "abandonment": False}


# --- step_efficiency / server_of ----------------------------------------


def test_step_efficiency():
    assert te.step_efficiency(0, 0) == 0.0
    assert te.step_efficiency(10, 0) == 0.0
    assert te.step_efficiency(10, 3) == 0.3


def test_server_of():
    assert te.server_of("mcp__memory-orchestrator__unified_search") == "memory-orchestrator"
    assert te.server_of("mcp__1c-mcp-crud__execute_query") == "1c-mcp-crud"
    assert te.server_of("Bash") == te.BUILTIN_BUCKET
    assert te.server_of(None) == te.BUILTIN_BUCKET
    assert te.server_of("mcp__weird") == te.BUILTIN_BUCKET  # no __op suffix


# --- rollup_by_server ----------------------------------------------------


def test_rollup_by_server_aggregates_and_computes_rates():
    stats = {
        "mcp__srv__a": {"calls": 8, "errors": 2, "repeats": 2, "abandonment": True},
        "mcp__srv__b": {"calls": 2, "errors": 0, "repeats": 0, "abandonment": False},
        "Bash": {"calls": 4, "errors": 0, "repeats": 1, "abandonment": False},
    }
    r = te.rollup_by_server(stats)
    srv = r["srv"]
    assert srv["calls"] == 10
    assert srv["errors"] == 2
    assert srv["success"] == 8
    assert srv["success_rate"] == 0.8
    assert srv["error_rate"] == 0.2
    assert srv["repeats"] == 2
    assert srv["step_efficiency"] == 0.2  # 2/10
    assert srv["abandonment_tools"] == 1
    assert srv["tools"] == 2
    assert r[te.BUILTIN_BUCKET]["calls"] == 4
    assert r[te.BUILTIN_BUCKET]["step_efficiency"] == 0.25  # 1/4


def test_rollup_by_server_zero_calls_safe():
    r = te.rollup_by_server({"mcp__s__t": {"calls": 0, "errors": 0}})
    assert r["s"]["success_rate"] == 1.0
    assert r["s"]["step_efficiency"] == 0.0


# --- P2.1: gen_ai.* aliases in invocation logger ------------------------


def test_gen_ai_aliases_written(tmp_path, monkeypatch):
    il = _load("_invocation_logger", ".claude/hooks/shared/invocation_logger.py")
    logf = tmp_path / "hook-invocations.jsonl"
    monkeypatch.setattr(il, "_LOG_FILE", logf)
    il.log_invocation(
        hook="X",
        event="PostToolUse",
        tool="mcp__srv__op",
        outcome="allow",
        category="mcp_call",
        tool_call_id="tc-1",
    )
    rec = json.loads(logf.read_text(encoding="utf-8").splitlines()[0])
    # aliases mirror the flat fields verbatim
    assert rec["gen_ai.tool.name"] == "mcp__srv__op" == rec["tool"]
    assert rec["gen_ai.tool.call.id"] == "tc-1" == rec["tool_call_id"]
    assert rec["error.type"] == rec["error_type"] == ""  # no error → empty


def test_gen_ai_error_type_alias_on_error(tmp_path, monkeypatch):
    il = _load("_invocation_logger2", ".claude/hooks/shared/invocation_logger.py")
    logf = tmp_path / "hook-invocations.jsonl"
    monkeypatch.setattr(il, "_LOG_FILE", logf)
    monkeypatch.setenv("CLAUDE_LOG_NO_CRYPTO", "1")
    il.log_invocation(hook="X", event="PostToolUse", tool="Bash", outcome="error")
    rec = json.loads(logf.read_text(encoding="utf-8").splitlines()[0])
    assert rec["error.type"] == "unknown" == rec["error_type"]
    assert rec["success"] is False
