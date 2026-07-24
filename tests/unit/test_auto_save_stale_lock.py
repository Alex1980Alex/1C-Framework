"""Stale .git/index.lock guard for the auto-save hook trio (2026-07-24).

Live incident: a 4.5-hour-old 0-byte index.lock left by a crashed auto-save
run blocked every subsequent commit in the main repo. clear_stale_index_lock
must remove orphaned locks but NEVER touch a fresh one (a live git process).
Runs against throwaway directories in tmp_path (no git binary needed).
"""

from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_CORE_PATH = (
    Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "shared" / "auto_save_core.py"
)
_spec = importlib.util.spec_from_file_location("auto_save_core", _CORE_PATH)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


def _make_lock(repo: Path, age_sec: float) -> Path:
    git_dir = repo / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    lock = git_dir / "index.lock"
    lock.write_bytes(b"")
    stamp = time.time() - age_sec
    os.utime(lock, (stamp, stamp))
    return lock


def test_stale_lock_removed(tmp_path: Path) -> None:
    lock = _make_lock(tmp_path, age_sec=3600)
    assert core.clear_stale_index_lock(str(tmp_path)) is True
    assert not lock.exists()


def test_fresh_lock_untouched(tmp_path: Path) -> None:
    lock = _make_lock(tmp_path, age_sec=5)
    assert core.clear_stale_index_lock(str(tmp_path)) is False
    assert lock.exists()


def test_no_lock_noop(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert core.clear_stale_index_lock(str(tmp_path)) is False


def test_threshold_boundary_respects_custom_age(tmp_path: Path) -> None:
    lock = _make_lock(tmp_path, age_sec=120)
    assert core.clear_stale_index_lock(str(tmp_path), max_age_sec=300) is False
    assert lock.exists()
    assert core.clear_stale_index_lock(str(tmp_path), max_age_sec=60) is True
    assert not lock.exists()
