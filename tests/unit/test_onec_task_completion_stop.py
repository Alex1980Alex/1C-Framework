"""Unit-тесты onec-task-completion-stop (единый task-completion gate 1С). marker: unit.

Collision-immune (importlib). Покрытие: _collect_signals (recall/capture/research/skill по фактическим
tool_use; .md-capture только в `.claude/`; Skill 1С-методики vs прочие), _onec_task_this_session (предикат).
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "onec-task-completion-stop.py"
_spec = importlib.util.spec_from_file_location("onec_task_completion_stop_t", _HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _transcript(p: Path, tool_uses: list[tuple[str, dict]]) -> None:
    p.write_text(
        "\n".join(
            json.dumps({"message": {"role": "assistant", "content": [{"type": "tool_use", "name": n, "input": i}]}})
            for n, i in tool_uses
        ),
        encoding="utf-8",
    )


def test_collect_all_signals(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [
        ("mcp__memory-orchestrator__unified_search", {}),
        ("mcp__skill-learning__capture_pattern", {}),
        ("WebSearch", {"query": "1с infostart"}),
        ("Skill", {"skill": "analyze-1c-task-v2"}),
    ])
    assert mod._collect_signals(str(t)) == {"recall": True, "capture": True, "research": True, "skill": True}


def test_collect_none(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [("Read", {"file_path": "x"}), ("Bash", {"command": "echo"})])
    assert mod._collect_signals(str(t)) == {"recall": False, "capture": False, "research": False, "skill": False}


def test_collect_partial(tmp_path):
    # recall + research есть, capture + skill нет
    t = tmp_path / "t.json"
    _transcript(t, [
        ("mcp__vector-memory__search_patterns", {}),
        ("WebFetch", {"url": "https://github.com/x"}),
    ])
    sig = mod._collect_signals(str(t))
    assert sig["recall"] and sig["research"] and not sig["capture"] and not sig["skill"]


def test_collect_md_capture_only_in_claude(tmp_path):
    # .md в курируемой памяти (`.claude/.../memory/`) = capture; src/memory/ — нет (N6)
    t = tmp_path / "t.json"
    _transcript(t, [("Write", {"file_path": "C:/Users/x/.claude/projects/p/memory/f.md"})])
    assert mod._collect_signals(str(t))["capture"] is True
    t2 = tmp_path / "t2.json"
    _transcript(t2, [("Write", {"file_path": "src/memory/README.md"})])
    assert mod._collect_signals(str(t2))["capture"] is False


def test_collect_skill_non_1c_not_counted(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [("Skill", {"skill": "deployment"})])
    assert mod._collect_signals(str(t))["skill"] is False


def test_onec_task_predicate(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PIPELINE_DIR", tmp_path)
    d = tmp_path / "task1"
    d.mkdir()
    (d / ".pipeline-state.json").write_text(
        json.dumps({"title": "1С-задача (run-1c-task): zz", "updated_at": "2027-01-01T00:00:00"}), encoding="utf-8"
    )
    assert mod._onec_task_this_session(datetime(2026, 6, 15)) is True
    assert mod._onec_task_this_session(None) is False


def test_onec_task_lookalike_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PIPELINE_DIR", tmp_path)
    d = tmp_path / "task1"
    d.mkdir()
    (d / ".pipeline-state.json").write_text(
        json.dumps({"title": "1С-задача из чата: x", "updated_at": "2027-01-01T00:00:00"}), encoding="utf-8"
    )
    assert mod._onec_task_this_session(datetime(2026, 6, 15)) is False
