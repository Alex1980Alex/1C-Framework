"""Amend-absorb regression for auto-save hook trio (2026-06-12).

get_amendable_head: consecutive auto-save commits must collapse via --amend,
but ONLY when safe — same prefix, unpushed, no merge in progress.
Runs against throwaway git repos in tmp_path (no network).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_CORE_PATH = (
    Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "shared" / "auto_save_core.py"
)
_spec = importlib.util.spec_from_file_location("auto_save_core", _CORE_PATH)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=15
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "master")
    _git(r, "config", "user.email", "test@test")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "base.py").write_text("x = 1\n", encoding="utf-8")
    _git(r, "add", "base.py")
    _git(r, "commit", "-m", "feat: base")
    return r


def _autosave_commit(repo: Path, fname: str = "a.py") -> None:
    (repo / fname).write_text("y = 2\n", encoding="utf-8")
    _git(repo, "add", fname)
    _git(repo, "commit", "-m", f"chore: auto-save {fname}")


def test_unpushed_autosave_head_is_amendable(repo: Path) -> None:
    _autosave_commit(repo, "a.py")
    files = core.get_amendable_head(str(repo))
    assert files == ["a.py"]


def test_meaningful_head_not_amendable(repo: Path) -> None:
    assert core.get_amendable_head(str(repo)) is None  # HEAD = "feat: base"


def test_prefix_mismatch_not_amendable(repo: Path) -> None:
    _autosave_commit(repo, "a.py")
    # sweep-drift и auto-commit не смешиваются с auto-save
    assert core.get_amendable_head(str(repo), prefix="chore: sweep unrelated drift") is None
    assert core.get_amendable_head(str(repo), prefix="chore: auto-commit") is None


def test_pushed_autosave_not_amendable(repo: Path, tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _autosave_commit(repo, "a.py")
    _git(repo, "push", "-u", "origin", "master")
    assert core.get_amendable_head(str(repo)) is None  # на remote — амендить нельзя


def test_merge_in_progress_not_amendable(repo: Path) -> None:
    _autosave_commit(repo, "a.py")
    git_dir = repo / ".git"
    (git_dir / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
    try:
        assert core.get_amendable_head(str(repo)) is None
    finally:
        (git_dir / "MERGE_HEAD").unlink()


def test_amend_flow_collapses_commits(repo: Path) -> None:
    """Сценарий хука: второй auto-save амендит первый → один коммит, union-сообщение."""
    _autosave_commit(repo, "a.py")
    (repo / "b.py").write_text("z = 3\n", encoding="utf-8")
    _git(repo, "add", "b.py")

    head_files = core.get_amendable_head(str(repo))
    assert head_files is not None
    msg = core.format_commit_message(core.merge_for_message(head_files, ["b.py"]))
    r = _git(repo, "commit", "--amend", "-m", msg)
    assert r.returncode == 0

    log = _git(repo, "log", "--format=%s").stdout.strip().splitlines()
    assert log == ["chore: auto-save a.py, b.py", "feat: base"]


def test_merge_for_message_dedupes_basenames() -> None:
    merged = core.merge_for_message(["src/a.py", "b.py"], ["C:/abs/path/a.py", "c.py"])
    assert merged == ["src/a.py", "b.py", "c.py"]
