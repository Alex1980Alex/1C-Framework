"""Guard: the ``scripts/git_hooks/`` directory must stay intact.

Why this exists
---------------
``git config core.hooksPath`` points at ``scripts/git_hooks``. The post-commit /
post-merge / post-checkout hooks there drive the incremental re-index automation
(BSL + framework). During the 2026-06 merge/autofix regression the *entire*
directory was deleted — which silently disabled every re-index hook with **zero**
error output (git just skips a missing hooksPath). It went unnoticed because no
test or CI step asserted the hooks exist.

This suite turns "directory silently gone" into a hard CI failure. It is marked
``unit`` (``pytestmark`` below) so the existing ``test-unit`` job
(``pytest tests/ -m unit``) runs it on every push / PR.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

# tests/unit/<this file> -> parents[2] == repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_DIR = _REPO_ROOT / "scripts" / "git_hooks"

# The three hooks that wire the re-index automation + the pre-push quality
# gate (added 2026-06-12 — before it, pushes left the machine unchecked:
# hooksPath shadows .git/hooks so the pre-commit framework never fired).
# Keep in sync with ``core.hooksPath`` and scripts/git_post_commit_reindex.py.
_REQUIRED_HOOKS = ["post-commit", "post-merge", "post-checkout", "pre-push"]


def test_git_hooks_dir_exists() -> None:
    assert _HOOKS_DIR.is_dir(), (
        f"{_HOOKS_DIR} is missing — core.hooksPath points here; its absence "
        "silently disables ALL re-index automation (the 2026-06 regression)."
    )


@pytest.mark.parametrize("hook_name", _REQUIRED_HOOKS)
def test_required_hook_present_and_non_empty(hook_name: str) -> None:
    hook = _HOOKS_DIR / hook_name
    assert hook.is_file(), f"required git hook {hook} is missing"
    assert hook.stat().st_size > 0, f"git hook {hook} is empty (truncated)"


def test_post_commit_wires_reindex() -> None:
    """post-commit must still invoke the incremental re-index entrypoint —
    catches a hook that survives as a file but lost its reindex wiring."""
    post_commit = (_HOOKS_DIR / "post-commit").read_text(encoding="utf-8", errors="replace")
    assert "git_post_commit_reindex.py" in post_commit, (
        "post-commit no longer references git_post_commit_reindex.py — "
        "re-index automation wiring was lost."
    )
