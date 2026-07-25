"""Регрессия W4 (ретро 260725): фаза task-protocol монотонна.

Фаза идёт idle → classified → decomposed → skill_checked, и только последняя пускает
Write/Edit через `task-protocol-enforcer`. `record_decomposition` писала 'decomposed'
БЕЗУСЛОВНО, поэтому порядок «активация скилла → TaskCreate → Write» откатывал уже
пройденный skill_checked и ронял легитимную запись в ложный блок «Decomposed but skills
not checked» (живьём - трижды за одну сессию).

Саботаж-проверка: убрать guard в `record_decomposition` → первый тест краснеет.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SS_PATH = _ROOT / ".claude" / "hooks" / "shared" / "session_state.py"


@pytest.fixture
def state(tmp_path, monkeypatch):
    """Свежий модуль session_state с изолированным state-файлом."""
    monkeypatch.setenv("SESSION_STATE_PATH", str(tmp_path))
    spec = importlib.util.spec_from_file_location(f"_ss_{tmp_path.name}", _SS_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.SessionState


def test_decomposition_after_skill_check_keeps_phase(state):
    """САБОТАЖ-ИНВАРИАНТ: TaskCreate ПОСЛЕ активации скилла не откатывает фазу."""
    state.record_skill_checked()
    assert state.get_task_protocol()["phase"] == "skill_checked"

    state.record_decomposition()

    p = state.get_task_protocol()
    assert p["phase"] == "skill_checked", "фаза откатилась - Write будет ложно заблокирован"
    assert p["subtask_count"] == 1, "счётчик подзадач растёт независимо от фазы"


def test_decomposition_before_skill_check_still_advances(state):
    """Прямой путь не сломан: без skill_checked TaskCreate ставит decomposed."""
    state.set_task_classified("complex")
    assert state.get_task_protocol()["phase"] == "classified"

    state.record_decomposition()
    assert state.get_task_protocol()["phase"] == "decomposed"


def test_skill_check_after_decomposition_advances(state):
    """decomposed → skill_checked: движение вперёд разрешено."""
    state.record_decomposition()
    state.record_skill_checked()
    assert state.get_task_protocol()["phase"] == "skill_checked"


def test_many_task_creates_keep_phase_and_count(state):
    """Несколько TaskCreate после skill_checked: счётчик растёт, фаза держится."""
    state.record_skill_checked()
    for _ in range(4):
        state.record_decomposition()

    p = state.get_task_protocol()
    assert p["phase"] == "skill_checked"
    assert p["subtask_count"] == 4


def test_reset_returns_to_idle(state):
    """Новый промпт (UserPromptSubmit) сбрасывает фазу - это штатно, не регрессия."""
    state.record_skill_checked()
    state.reset_task_protocol()
    assert state.get_task_protocol()["phase"] == "idle"
