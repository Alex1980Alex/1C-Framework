"""Unit: SessionState._save_state — атомарная запись (защита от corruption при гонке хуков)."""

import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "hooks"))

pytestmark = pytest.mark.unit


def _fresh(monkeypatch, tmp_path):
    monkeypatch.setenv("SESSION_STATE_PATH", str(tmp_path))
    from shared import session_state as ss

    importlib.reload(ss)
    ss.SessionState._state_cache = None
    return ss


def test_save_produces_valid_json_no_temp_leftover(monkeypatch, tmp_path):
    ss = _fresh(monkeypatch, tmp_path)
    ss.SessionState.add_activated_skill("duckdb-analytics")

    data = json.loads((tmp_path / "session-skills.json").read_text(encoding="utf-8"))
    assert "duckdb-analytics" in data["activated_skills"]
    # atomic write не оставляет stray temp-файлов
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_repeated_saves_stay_valid(monkeypatch, tmp_path):
    ss = _fresh(monkeypatch, tmp_path)
    for i in range(20):
        ss.SessionState.add_activated_skill(f"skill-{i}")

    data = json.loads((tmp_path / "session-skills.json").read_text(encoding="utf-8"))
    assert len(data["activated_skills"]) == 20
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_skill_checked_phase_persists(monkeypatch, tmp_path):
    ss = _fresh(monkeypatch, tmp_path)
    ss.SessionState.record_skill_checked()

    # читаем заново через свежий load — фаза должна сохраниться валидной
    ss.SessionState._state_cache = None
    assert ss.SessionState.get_task_protocol().get("phase") == "skill_checked"
