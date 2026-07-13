"""Регрессия P0-фиксов аудита логирования инструментов (roadmap 260713).

P0.1 (B1): detected_event классифицирует PostToolUse по `tool_response`
           (modern) с легаси-фоллбэком `tool_result`; hook_event_name — приоритет.
P0.2 (B2): HookInput.agent_id читается из payload; BaseHook.run() прокидывает его
           в log_invocation (сейчас платформа его не шлёт → "" , но проводка есть).
P0.4 (B4): BaseHook.run() подавляет ДУБЛЬ-автолог для mcp__ тула при outcome=allow
           (канонический row пишет mcp-invocation-logger); block/error — сохраняются.

Без сети/реального лога: log_invocation и run_context замоканы через sys.modules,
stdin — через подмену HookInput.from_stdin.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

_PROTOCOL_PATH = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "base" / "protocol.py"
_spec = importlib.util.spec_from_file_location("_protocol_p0", _PROTOCOL_PATH)
proto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(proto)

HookInput = proto.HookInput
HookOutput = proto.HookOutput
BaseHook = proto.BaseHook


# ── P0.1 (B1): detected_event ────────────────────────────────────────────────


def test_b1_post_detected_via_tool_response():
    """Modern payload: tool_name + tool_response, без hook_event_name → PostToolUse."""
    inp = HookInput({"tool_name": "Bash", "tool_response": {"stdout": "ok"}})
    assert inp.detected_event == "PostToolUse"


def test_b1_post_detected_via_legacy_tool_result():
    """Легаси payload: tool_result всё ещё распознаётся как Post."""
    inp = HookInput({"tool_name": "Bash", "tool_result": "ok"})
    assert inp.detected_event == "PostToolUse"


def test_b1_pre_when_no_result():
    """tool_name без результата → PreToolUse (без ложного Post)."""
    inp = HookInput({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert inp.detected_event == "PreToolUse"


def test_b1_hook_event_name_priority_over_response():
    """hook_event_name авторитетен: Pre даже при наличии tool_response."""
    inp = HookInput({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_response": {}})
    assert inp.detected_event == "PreToolUse"


# ── P0.2 (B2): agent_id parsing ──────────────────────────────────────────────


def test_b2_agent_id_snake_case():
    assert HookInput({"agent_id": "xyz789"}).agent_id == "xyz789"


def test_b2_agent_id_camel_case_fallback():
    assert HookInput({"agentId": "abc123"}).agent_id == "abc123"


def test_b2_agent_id_absent_is_empty():
    assert HookInput({"tool_name": "Read"}).agent_id == ""


# ── B2 wiring + B4 dedup: BaseHook.run() logging behaviour ───────────────────


class _Recorder:
    """Фейк log_invocation — записывает kwargs каждого вызова."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


def _run_hook(monkeypatch, payload: dict, output):
    """Прогнать BaseHook.run() с замоканным логгером; вернуть Recorder."""
    rec = _Recorder()

    # Фейк-пакет shared + подмодули (sys.modules приоритетнее реального disk-пакета).
    shared_pkg = ModuleType("shared")
    shared_pkg.__path__ = []  # mark as package
    inv_mod = ModuleType("shared.invocation_logger")
    inv_mod.log_invocation = rec
    rc_mod = ModuleType("shared.run_context")
    rc_mod.get_run_id = lambda _sid: ""
    monkeypatch.setitem(sys.modules, "shared", shared_pkg)
    monkeypatch.setitem(sys.modules, "shared.invocation_logger", inv_mod)
    monkeypatch.setitem(sys.modules, "shared.run_context", rc_mod)

    class _Hook(BaseHook):
        def execute(self, inp):
            return output

    monkeypatch.setattr(HookInput, "from_stdin", classmethod(lambda cls: cls(payload)))
    _Hook().run()
    return rec


def test_b2_agent_id_forwarded_to_logger(monkeypatch):
    """agent_id из payload долетает до log_invocation."""
    rec = _run_hook(
        monkeypatch,
        {"tool_name": "Read", "tool_input": {}, "agent_id": "sub42", "session_id": "s1"},
        None,
    )
    assert len(rec.calls) == 1
    assert rec.calls[0]["agent_id"] == "sub42"


def test_b4_mcp_allow_dup_suppressed(monkeypatch):
    """mcp__ тул + outcome=allow → автолог ПОДАВЛЕН (канонический row у mcp-логгера)."""
    rec = _run_hook(
        monkeypatch,
        {"tool_name": "mcp__llm-rotation__llm_complete", "tool_input": {}, "session_id": "s1"},
        None,
    )
    assert rec.calls == []


def test_b4_mcp_block_still_logged(monkeypatch):
    """mcp__ тул + block → row СОХРАНЯЕТСЯ (несёт hook-специфичный сигнал)."""
    rec = _run_hook(
        monkeypatch,
        {"tool_name": "mcp__x__y", "tool_input": {}, "session_id": "s1"},
        HookOutput().block("nope"),
    )
    assert len(rec.calls) == 1
    assert rec.calls[0]["outcome"] == "block"


def test_b4_native_tool_still_logged(monkeypatch):
    """Нативный тул (не mcp__) + allow → row пишется как прежде (не затронут P0.4)."""
    rec = _run_hook(
        monkeypatch,
        {"tool_name": "Bash", "tool_input": {"command": "ls"}, "session_id": "s1"},
        None,
    )
    assert len(rec.calls) == 1
    assert rec.calls[0]["tool"] == "Bash"
    assert rec.calls[0]["outcome"] == "allow"
