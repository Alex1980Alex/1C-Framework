"""Unit: factory-enforcer SKIP_PATHS — библиотеки hooks/shared|base НЕ плодят ШАГ 4/5.

Регрессия: `engagement_rank.py` (shared-библиотека) ложно классифицировался как event-hook
→ фантомные «ШАГ 4 register / ШАГ 5 verify». Фикс — `/hooks/shared/` + `/hooks/base/` в SKIP_PATHS.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

_IMPORT_OK = True
try:
    _spec = importlib.util.spec_from_file_location(
        "factory_enforcer", _HOOKS / "factory-enforcer.py"
    )
    _fe = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_fe)
except Exception:
    _IMPORT_OK = False

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(not _IMPORT_OK, reason="factory-enforcer import failed"),
]


def _inp(path: str) -> SimpleNamespace:
    return SimpleNamespace(tool_name="Write", tool_input={"file_path": path})


def test_shared_lib_skipped():
    fe = _fe.FactoryEnforcer()
    assert fe.execute(_inp(r"C:\1С-Framework\.claude\hooks\shared\engagement_rank.py")) is None


def test_base_lib_skipped():
    fe = _fe.FactoryEnforcer()
    assert fe.execute(_inp("/x/.claude/hooks/base/protocol.py")) is None


def test_toplevel_hook_still_detected(monkeypatch):
    # нейтрализуем сайд-эффекты (без мутации реального hook-todos.json)
    monkeypatch.setattr(_fe, "has_recent_completion", lambda *a, **k: False)
    monkeypatch.setattr(_fe, "get_pending_tasks", lambda *a, **k: [])
    created: list[str] = []
    monkeypatch.setattr(_fe, "add_task", lambda **k: created.append(k.get("title", "")))
    fe = _fe.FactoryEnforcer()
    out = fe.execute(_inp("/x/.claude/hooks/my-new-hook.py"))
    assert out is not None  # top-level .py → распознан как hook
    assert len(created) == 2  # ШАГ 4 + ШАГ 5


def test_skill_md_still_detected(monkeypatch):
    monkeypatch.setattr(_fe, "has_recent_completion", lambda *a, **k: False)
    monkeypatch.setattr(_fe, "get_pending_tasks", lambda *a, **k: [])
    monkeypatch.setattr(_fe, "add_task", lambda **k: None)
    fe = _fe.FactoryEnforcer()
    out = fe.execute(_inp("/x/.claude/skills/foo/SKILL.md"))
    assert out is not None  # скиллы по-прежнему детектятся
