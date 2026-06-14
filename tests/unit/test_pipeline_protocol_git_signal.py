"""Регрессия второго сигнала «была правка» через git для pipeline-protocol-stop.

`_git_session_edit` закрывает пробел инструментов без PreToolUse-матчера
(MultiEdit/NotebookEdit): незакоммиченный обычный файл, изменённый ЗА сессию
(mtime >= start) и не в denylist → правка. Без сети/реального git —
`subprocess.run` замокан, mtime файлов в tmp_path управляется через os.utime.
"""

from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOK_PATH = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "pipeline-protocol-stop.py"
_spec = importlib.util.spec_from_file_location("pipeline_protocol_stop", _HOOK_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


class _FakeProc:
    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode


def _patch_git(monkeypatch, stdout: str, returncode: int = 0, counter: dict | None = None):
    def fake_run(*_a, **_k):
        if counter is not None:
            counter["n"] += 1
        return _FakeProc(stdout, returncode)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)


def _mk(tmp_path: Path, rel: str, mtime_offset_min: float) -> Path:
    """Создать файл с mtime = now + offset (минуты, отрицательное = в прошлом)."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x\n", encoding="utf-8")
    t = (datetime.now() + timedelta(minutes=mtime_offset_min)).timestamp()
    os.utime(p, (t, t))
    return p


def test_modified_in_session_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    _mk(tmp_path, "src/x.py", mtime_offset_min=0)  # mtime ~ now
    _patch_git(monkeypatch, " M src/x.py\n")
    start = datetime.now() - timedelta(minutes=5)  # сессия началась раньше правки
    assert mod._git_session_edit(start) is True


def test_pre_session_dirty_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    _mk(tmp_path, "src/old.py", mtime_offset_min=-120)  # правлен 2ч назад
    _patch_git(monkeypatch, " M src/old.py\n")
    start = datetime.now() - timedelta(minutes=5)  # сессия началась ПОСЛЕ правки
    assert mod._git_session_edit(start) is False


def test_denylisted_autowrite_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    _mk(tmp_path, "docs/wiki/log.md", mtime_offset_min=0)  # свежий, но авто-артефакт
    _patch_git(monkeypatch, " M docs/wiki/log.md\n")
    start = datetime.now() - timedelta(minutes=5)
    assert mod._git_session_edit(start) is False


def test_start_none_short_circuits_without_git(monkeypatch):
    counter = {"n": 0}
    _patch_git(monkeypatch, " M src/x.py\n", counter=counter)
    assert mod._git_session_edit(None) is False
    assert counter["n"] == 0  # git не вызывается без start


def test_git_error_returns_false(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    _mk(tmp_path, "src/x.py", mtime_offset_min=0)
    _patch_git(monkeypatch, "", returncode=1)
    assert mod._git_session_edit(datetime.now() - timedelta(minutes=5)) is False


def test_submodule_or_dir_entry_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    (tmp_path / "configuration" / "sub").mkdir(parents=True)  # каталог (как сабмодуль)
    _patch_git(monkeypatch, " M configuration/sub\n")
    start = datetime.now() - timedelta(minutes=5)
    assert mod._git_session_edit(start) is False


def test_rename_uses_destination_path(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    _mk(tmp_path, "new.py", mtime_offset_min=0)  # dest существует и свежий
    _patch_git(monkeypatch, "R  old.py -> new.py\n")
    start = datetime.now() - timedelta(minutes=5)
    assert mod._git_session_edit(start) is True


def test_untracked_collapsed_dir_detected(tmp_path, monkeypatch):
    # `?? newpkg/` — git схлопывает новый каталог; mtime каталога свежий → правка за сессию
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    d = tmp_path / "newpkg"
    d.mkdir()
    (d / "mod.py").write_text("a\n", encoding="utf-8")  # mtime каталога обновился ~ now
    _patch_git(monkeypatch, "?? newpkg/\n")
    start = datetime.now() - timedelta(minutes=5)
    assert mod._git_session_edit(start) is True


def test_untracked_collapsed_dir_pre_session_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    d = tmp_path / "oldpkg"
    d.mkdir()
    old = (datetime.now() - timedelta(hours=2)).timestamp()
    os.utime(d, (old, old))  # каталог не трогался за сессию
    _patch_git(monkeypatch, "?? oldpkg/\n")
    start = datetime.now() - timedelta(minutes=5)
    assert mod._git_session_edit(start) is False
