"""Регрессия P0.3 (roadmap 260713): канонический tool-invocation-logger + обобщение потребителя.

tool-invocation-logger пишет ОДНУ строку category="tool_call" на built-in вызов
(tool_call_id + args_hash), no-op на mcp__/неизвестных тулах, без дубль-автолога.
tool_usage_report.aggregate теперь считает tool_call как mcp_call (реальная Pre/Post
латентность + дедуп calls).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_HOOK_PATH = _ROOT / ".claude" / "hooks" / "tool-invocation-logger.py"
_TUR_PATH = _ROOT / "scripts" / "tool_usage_report.py"


def _load_logger(monkeypatch):
    """Загрузить hook с замоканным shared.* (sys.modules приоритетнее disk-пакета)."""
    calls: list[dict] = []
    shared_pkg = ModuleType("shared")
    shared_pkg.__path__ = []
    inv = ModuleType("shared.invocation_logger")
    inv.log_invocation = lambda **k: calls.append(k)
    rc = ModuleType("shared.run_context")
    rc.get_run_id = lambda _s: ""
    monkeypatch.setitem(sys.modules, "shared", shared_pkg)
    monkeypatch.setitem(sys.modules, "shared.invocation_logger", inv)
    monkeypatch.setitem(sys.modules, "shared.run_context", rc)
    spec = importlib.util.spec_from_file_location("_tool_inv_logger", _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, calls


def test_p03_builtin_emits_tool_call_row(monkeypatch):
    """Built-in Post-вызов → одна строка category=tool_call с tool_call_id/args_hash."""
    mod, calls = _load_logger(monkeypatch)
    HookInput = sys.modules["base"].HookInput  # imported by the hook
    inp = HookInput(
        {
            "tool_name": "Read",
            "tool_input": {"file_path": "x.py"},
            "tool_response": {"content": [{"text": "ok"}]},
            "tool_use_id": "tu_1",
            "session_id": "s1",
        }
    )
    mod.ToolInvocationLogger().execute(inp)
    assert len(calls) == 1
    row = calls[0]
    assert row["category"] == "tool_call"
    assert row["event"] == "PostToolUse"
    assert row["tool"] == "Read"
    assert row["tool_call_id"] == "tu_1"
    assert row["args_hash"]  # непустой фингерпринт


def test_p03_mcp_tool_is_noop(monkeypatch):
    """mcp__ тул НЕ логируется этим хуком (его канон — mcp-invocation-logger)."""
    mod, calls = _load_logger(monkeypatch)
    HookInput = sys.modules["base"].HookInput
    inp = HookInput({"tool_name": "mcp__x__y", "tool_input": {}, "session_id": "s1"})
    mod.ToolInvocationLogger().execute(inp)
    assert calls == []


def test_p03_unknown_tool_is_noop(monkeypatch):
    """Тул вне BUILTIN_TOOLS → no-op (оставлен автологу)."""
    mod, calls = _load_logger(monkeypatch)
    HookInput = sys.modules["base"].HookInput
    inp = HookInput({"tool_name": "SomeFutureTool", "tool_input": {}, "session_id": "s1"})
    mod.ToolInvocationLogger().execute(inp)
    assert calls == []


def test_p03_error_marker_classified(monkeypatch):
    """tool_response со строкой 'Error:' → outcome=error, error_type=tool_error."""
    mod, calls = _load_logger(monkeypatch)
    HookInput = sys.modules["base"].HookInput
    inp = HookInput(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "x"},
            "tool_response": {"content": [{"text": "Error: boom"}]},
            "session_id": "s1",
        }
    )
    mod.ToolInvocationLogger().execute(inp)
    assert calls[0]["outcome"] == "error"
    assert calls[0]["error_type"] == "tool_error"


def test_p03_pre_event_no_error(monkeypatch):
    """Pre-вызов (нет tool_response) → outcome=allow (ошибка только в Post)."""
    mod, calls = _load_logger(monkeypatch)
    HookInput = sys.modules["base"].HookInput
    inp = HookInput({"tool_name": "Grep", "tool_input": {"pattern": "x"}, "session_id": "s1"})
    mod.ToolInvocationLogger().execute(inp)
    assert calls[0]["event"] == "PreToolUse"
    assert calls[0]["outcome"] == "allow"


# ── потребитель: tool_usage_report обобщён на tool_call ───────────────────────


def _load_tur():
    spec = importlib.util.spec_from_file_location("_tur", _TUR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tur_counts_tool_call_like_mcp(tmp_path):
    """aggregate() считает tool_call как канонический вызов: Pre+Post = 1 calls, реальная латентность."""
    import json

    tur = _load_tur()
    log = tmp_path / "log.jsonl"
    rows = [
        {
            "ts": "2026-07-14T10:00:00.000",
            "tool": "Read",
            "event": "PreToolUse",
            "category": "tool_call",
            "correlationid": "run1",
            "tool_call_id": "tu1",
            "outcome": "allow",
        },
        {
            "ts": "2026-07-14T10:00:00.200",
            "tool": "Read",
            "event": "PostToolUse",
            "category": "tool_call",
            "correlationid": "run1",
            "tool_call_id": "tu1",
            "outcome": "allow",
        },
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    agg = tur.aggregate(run_id="run1", log=log)
    assert set(agg) == {"Read"}
    assert agg["Read"]["calls"] == 1  # Pre+Post одного вызова не двоятся
    assert agg["Read"]["latency_real"] is True
    assert agg["Read"]["ms"] == 200  # реальная Pre→Post длительность


def test_tur_tool_call_stray_hook_rows_not_doubled(tmp_path):
    """category=hook строки того же built-in тула не двоят canonical calls."""
    import json

    tur = _load_tur()
    log = tmp_path / "log.jsonl"
    rows = [
        {
            "ts": "2026-07-14T10:00:00.000",
            "tool": "Bash",
            "event": "PreToolUse",
            "category": "tool_call",
            "correlationid": "run1",
            "tool_call_id": "tu1",
        },
        {
            "ts": "2026-07-14T10:00:00.100",
            "tool": "Bash",
            "event": "PostToolUse",
            "category": "tool_call",
            "correlationid": "run1",
            "tool_call_id": "tu1",
        },
        # шумовые энфомер-строки (SearchOptimizer/BulkActionGuard) того же вызова:
        {
            "ts": "2026-07-14T10:00:00.050",
            "tool": "Bash",
            "event": "PreToolUse",
            "category": "hook",
            "correlationid": "run1",
        },
        {
            "ts": "2026-07-14T10:00:00.051",
            "tool": "Bash",
            "event": "PreToolUse",
            "category": "hook",
            "correlationid": "run1",
        },
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    agg = tur.aggregate(run_id="run1", log=log)
    assert agg["Bash"]["calls"] == 1  # не 3: hook-строки не двоят canonical вызов
