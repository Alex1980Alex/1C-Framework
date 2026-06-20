"""Unit-тесты check_submodule_push_order (ADR-027): pre-push submodule-ordering guard.

Детерминированы (marker `unit`): мокаем `_run` (git-вызовы) → проверяем вердикт main().
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_submodule_push_order.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_submodule_push_order", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _R:
    def __init__(self, rc=0, out=""):
        self.returncode = rc
        self.stdout = out
        self.stderr = ""


def _make_fake_run(new_sha="NEWSHA", old_sha="OLDSHA", on_remote_out="", initialized=True):
    def fake_run(args):
        a = args
        if a[:4] == ["git", "config", "-f", ".gitmodules"]:
            return _R(0, "submodule.A.path sub/A\n")
        if a[:2] == ["git", "ls-tree"]:
            rev = a[2]
            sha = new_sha if rev == "LSHA" else old_sha
            return _R(0, f"160000 commit {sha}\tsub/A\n")
        if a[:3] == ["git", "-C", "sub/A"] and "rev-parse" in a:
            return _R(0 if initialized else 128, ".git/modules/sub/A\n" if initialized else "")
        if a[:3] == ["git", "-C", "sub/A"] and "branch" in a:
            return _R(0, on_remote_out)
        return _R(0, "")

    return fake_run


@pytest.mark.unit
def test_blocks_when_submodule_commit_not_on_remote(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_run", _make_fake_run(on_remote_out=""))  # не на remote
    assert m.main(["x", "BASE", "LSHA"]) == 1


@pytest.mark.unit
def test_allows_when_commit_on_remote(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_run", _make_fake_run(on_remote_out="  origin/master\n"))
    assert m.main(["x", "BASE", "LSHA"]) == 0


@pytest.mark.unit
def test_allows_when_gitlink_unchanged(monkeypatch):
    m = _load()
    # new == old → сабмодуль не изменён в диапазоне → пропуск
    monkeypatch.setattr(m, "_run", _make_fake_run(new_sha="SAME", old_sha="SAME"))
    assert m.main(["x", "BASE", "LSHA"]) == 0


@pytest.mark.unit
def test_allows_when_submodule_not_initialized(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_run", _make_fake_run(on_remote_out="", initialized=False))
    assert m.main(["x", "BASE", "LSHA"]) == 0


@pytest.mark.unit
def test_noop_without_args():
    m = _load()
    assert m.main(["x"]) == 0
