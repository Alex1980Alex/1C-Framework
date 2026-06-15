"""Unit-тесты research-protocol-stop (Stop-энфорсер обязательного внешнего анализа для 1С-задач). marker: unit.

Collision-immune: хук загружается по пути через importlib. Покрытие: _research_done (WebSearch/WebFetch
по ФАКТИЧЕСКИМ tool_use; прочие → False), _onec_task_this_session (title '1С-задача (' + dt>=start;
non-1C/lookalike/start=None → False).
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "research-protocol-stop.py"
_spec = importlib.util.spec_from_file_location("research_protocol_stop_t", _HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _transcript(p: Path, tool_uses: list[tuple[str, dict]]) -> None:
    lines = [
        json.dumps({"message": {"role": "assistant", "content": [{"type": "tool_use", "name": n, "input": i}]}})
        for n, i in tool_uses
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def test_research_done_websearch(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [("WebSearch", {"query": "1С проведение инфостарт"})])
    assert mod._research_done(str(t)) is True


def test_research_done_webfetch(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [("WebFetch", {"url": "https://infostart.ru/x"})])
    assert mod._research_done(str(t)) is True


def test_research_not_done(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [("Read", {"file_path": "x"}), ("Bash", {"command": "echo"})])
    assert mod._research_done(str(t)) is False


def test_research_missing_transcript():
    assert mod._research_done("") is False
    assert mod._research_done("/no/such/transcript.json") is False


def test_onec_task_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PIPELINE_DIR", tmp_path)
    d = tmp_path / "task1"
    d.mkdir()
    (d / ".pipeline-state.json").write_text(
        json.dumps({"title": "1С-задача (analyze-1c-task): zz", "updated_at": "2027-01-01T00:00:00"}),
        encoding="utf-8",
    )
    assert mod._onec_task_this_session(datetime(2026, 6, 15)) is True
    assert mod._onec_task_this_session(None) is False


def test_onec_task_lookalike_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PIPELINE_DIR", tmp_path)
    d = tmp_path / "task1"
    d.mkdir()
    (d / ".pipeline-state.json").write_text(
        json.dumps({"title": "1С-задача из чата: классификатор", "updated_at": "2027-01-01T00:00:00"}),
        encoding="utf-8",
    )
    assert mod._onec_task_this_session(datetime(2026, 6, 15)) is False
