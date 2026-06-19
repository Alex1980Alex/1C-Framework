"""Regression: debounce auto-save hook must honor the pause sentinel (2026-06-19).

posttooluse-auto-git-save.py defined `_is_paused()` but never called it — the
debounce / --no-verify commit path fired straight through a `forever` pause
(sweeping unrelated staged files into auto-commits). The other two auto-save
hooks (auto-git-save.py, auto-git-save-prompt.py) gate on the same sentinel;
this guards the restored call site so the regression cannot silently return.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
_HOOK_PATH = _HOOKS_DIR / "posttooluse-auto-git-save.py"


def _load_hook():
    # The hook imports `base` / `shared` — make the hooks dir importable first.
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("posttooluse_auto_git_save", _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_hook()


def _fake_input(file_path: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(tool_input={"file_path": file_path})


def test_paused_skips_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    monkeypatch.setattr(mod, "_is_paused", lambda: True)
    monkeypatch.setattr(mod, "_git_commit", lambda files: calls.append(files) or True)

    mod.PostToolUseAutoGitSave().execute(_fake_input("src/x.py"))

    assert calls == []  # paused -> commit must NOT be attempted


def test_not_paused_commits_when_debounce_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    monkeypatch.setattr(mod, "_is_paused", lambda: False)
    monkeypatch.setattr(mod, "_git_commit", lambda files: calls.append(files) or True)
    # last_commit=0 -> debounce window long expired -> commit is due.
    monkeypatch.setattr(mod, "_load_pending", lambda: {"files": [], "last_commit": 0})
    monkeypatch.setattr(mod, "_save_pending", lambda data: None)

    mod.PostToolUseAutoGitSave().execute(_fake_input("src/x.py"))

    # Guards against over-gating: when NOT paused the commit must still happen.
    assert calls and "src/x.py" in calls[0]
