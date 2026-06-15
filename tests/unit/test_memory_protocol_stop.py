"""Unit-тесты memory-protocol-stop (Stop-энфорсер обязательного memory-цикла для 1С-задач). marker: unit.

Collision-immune: хук загружается по пути через importlib (имя с дефисами не импортируется как модуль;
shared.* не трогаем — `InvocationTimer` импортируется внутри main(), не при загрузке модуля).
Покрытие: _iter_tool_uses (парс tool_use), _memory_signals (recall/capture по ФАКТИЧЕСКИМ tool_use +
.md-write=capture), _onec_task_this_session (title '1С-задача' + dt>=start; non-1C/start=None → False).
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "memory-protocol-stop.py"
_spec = importlib.util.spec_from_file_location("memory_protocol_stop_t", _HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _transcript(p: Path, tool_uses: list[tuple[str, dict]]) -> None:
    lines = [
        json.dumps({"message": {"role": "assistant", "content": [{"type": "tool_use", "name": n, "input": i}]}})
        for n, i in tool_uses
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def test_iter_tool_uses_extracts_names():
    entry = {"message": {"content": [
        {"type": "tool_use", "name": "Foo", "input": {}},
        {"type": "text", "text": "ignore"},
    ]}}
    assert [t["name"] for t in mod._iter_tool_uses(entry)] == ["Foo"]


def test_memory_signals_none(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [("Write", {"file_path": "src/foo.bsl"}), ("Bash", {"command": "echo"})])
    assert mod._memory_signals(str(t)) == (False, False)


def test_memory_signals_both_tools(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [
        ("mcp__memory-orchestrator__unified_search", {"query": "x"}),
        ("mcp__skill-learning__capture_pattern", {}),
    ])
    assert mod._memory_signals(str(t)) == (True, True)


def test_memory_signals_md_write_is_capture(tmp_path):
    # запись в memory/*.md = capture; search_patterns = recall
    t = tmp_path / "t.json"
    _transcript(t, [
        ("mcp__vector-memory__search_patterns", {}),
        ("Write", {"file_path": "C:/x/memory/feedback_y.md"}),
    ])
    assert mod._memory_signals(str(t)) == (True, True)


def test_memory_signals_route_and_save_is_capture(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [
        ("mcp__memory-orchestrator__unified_search", {}),
        ("mcp__memory-orchestrator__route_and_save", {}),
    ])
    assert mod._memory_signals(str(t)) == (True, True)


def test_onec_task_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PIPELINE_DIR", tmp_path)
    d = tmp_path / "task1"
    d.mkdir()
    (d / ".pipeline-state.json").write_text(
        json.dumps({"title": "1С-задача (run-1c-task): zz", "updated_at": "2027-01-01T00:00:00"}),
        encoding="utf-8",
    )
    assert mod._onec_task_this_session(datetime(2026, 6, 15)) is True
    assert mod._onec_task_this_session(None) is False  # conservative: окно неизвестно → не блокируем


def test_onec_task_non_1c_title_ignored(tmp_path, monkeypatch):
    # framework/docs-пайплайн (не '1С-задача') → НЕ считается 1С-задачей
    monkeypatch.setattr(mod, "PIPELINE_DIR", tmp_path)
    d = tmp_path / "task1"
    d.mkdir()
    (d / ".pipeline-state.json").write_text(
        json.dumps({"title": "B' доработка: docs", "updated_at": "2027-01-01T00:00:00"}),
        encoding="utf-8",
    )
    assert mod._onec_task_this_session(datetime(2026, 6, 15)) is False


def test_onec_task_lookalike_title_excluded(tmp_path, monkeypatch):
    # framework-пайплайн «1С-задача из чата: …» (без открывающей скобки) ≠ реальная 1С-задача
    monkeypatch.setattr(mod, "PIPELINE_DIR", tmp_path)
    d = tmp_path / "task1"
    d.mkdir()
    (d / ".pipeline-state.json").write_text(
        json.dumps({"title": "1С-задача из чата: классификатор", "updated_at": "2027-01-01T00:00:00"}),
        encoding="utf-8",
    )
    assert mod._onec_task_this_session(datetime(2026, 6, 15)) is False


def test_onec_task_stale_pipeline_ignored(tmp_path, monkeypatch):
    # 1С-задача-пайплайн из ПРОШЛОЙ сессии (updated_at < start) → не считается текущей
    monkeypatch.setattr(mod, "PIPELINE_DIR", tmp_path)
    d = tmp_path / "task1"
    d.mkdir()
    (d / ".pipeline-state.json").write_text(
        json.dumps({"title": "1С-задача (analyze-1c-task): old", "updated_at": "2020-01-01T00:00:00"}),
        encoding="utf-8",
    )
    assert mod._onec_task_this_session(datetime(2026, 6, 15)) is False
