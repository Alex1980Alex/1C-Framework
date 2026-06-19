"""Regression for format_staged_python — auto-commit keeps .py CI-clean (2026-06-19).

Auto-commit paths use --no-verify (bypassing pre-commit), so unformatted .py
used to land in master and turn CI's Pre-commit Hooks job red
(memory project-ci-precommit-red-autocommit-noverify). format_staged_python
ruff-formats staged .py at the repo line-length before the commit.

Self-contained guard: runs ruff against throwaway repos in tmp_path (no network).
Skips gracefully if ruff is unavailable in the test environment.
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


def _ruff_available() -> bool:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "ruff", "--version"],
            capture_output=True,
            timeout=15,
        )
        return r.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


_NEEDS_RUFF = pytest.mark.skipif(not _ruff_available(), reason="ruff not installed")

# A line > 100 chars that ruff-format (line-length 100) must wrap.
_UNFORMATTED = (
    "def _probe(alpha, beta, gamma, delta, epsilon, zeta):\n"
    "    return alpha == 1 or beta == 2 or gamma == 3 or delta == 4 "
    "or epsilon == 5 or zeta == 6 or alpha > 99\n"
)


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
    (r / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
    return r


@_NEEDS_RUFF
def test_reformats_and_restages_long_line(repo: Path) -> None:
    f = repo / "mod.py"
    f.write_text(_UNFORMATTED, encoding="utf-8")
    assert any(len(line) > 100 for line in _UNFORMATTED.splitlines())  # precondition

    core.format_staged_python(str(repo), ["mod.py"])

    out = f.read_text(encoding="utf-8")
    # Core property: no line exceeds the configured width after formatting.
    assert all(len(line) <= 100 for line in out.splitlines())
    assert out != _UNFORMATTED  # actually changed
    # Re-staged into the index.
    staged = _git(repo, "diff", "--cached", "--name-only").stdout.split()
    assert "mod.py" in staged


@_NEEDS_RUFF
def test_skips_vendored_tree(repo: Path) -> None:
    vendored = repo / "tools" / "x.py"
    vendored.parent.mkdir(parents=True)
    vendored.write_text(_UNFORMATTED, encoding="utf-8")

    core.format_staged_python(str(repo), ["tools/x.py"])

    # tools/ mirrors the pre-commit exclude → left untouched.
    assert vendored.read_text(encoding="utf-8") == _UNFORMATTED


@_NEEDS_RUFF
def test_skips_vendored_absolute_path(repo: Path) -> None:
    vendored = repo / "src" / "bsl" / "y.py"
    vendored.parent.mkdir(parents=True)
    vendored.write_text(_UNFORMATTED, encoding="utf-8")

    # Hooks may pass absolute paths — skip-prefix must still match.
    core.format_staged_python(str(repo), [str(vendored)])

    assert vendored.read_text(encoding="utf-8") == _UNFORMATTED


def test_best_effort_never_raises(repo: Path) -> None:
    # Non-.py, missing file, and empty list must not raise (commit must proceed).
    core.format_staged_python(str(repo), ["notes.md", "gone.py", "data.json"])
    core.format_staged_python(str(repo), [])


def test_ruff_line_length_reads_pyproject(repo: Path) -> None:
    assert core._ruff_line_length(str(repo)) == 100


def test_ruff_line_length_fallback(tmp_path: Path) -> None:
    # No pyproject.toml → default.
    assert core._ruff_line_length(str(tmp_path)) == 100
    assert core._ruff_line_length(str(tmp_path), default=120) == 120
