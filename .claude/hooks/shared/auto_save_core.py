"""Shared helpers for auto-git-save hook trio.

Phase C1 closure (2026-05-15, roadmap 260515): rather than full consolidation
(which removes 3-layer redundancy intentionally maintained for Claude Code
#6305 workaround on Windows), extract DRY helpers used identically by all
three hooks:

  - auto-git-save.py            (threshold-based commit)
  - posttooluse-auto-git-save.py (5s debounce + --no-verify)
  - auto-git-save-prompt.py     (UPS fallback)

Single source of truth for the filename-list commit message format
(introduced 2026-05-14 — basenames of first N files + `+M more` suffix).
"""

from __future__ import annotations

import os
from collections.abc import Iterable

DEFAULT_MAX_DISPLAY = 3


def format_commit_message(
    files: Iterable[str],
    prefix: str = "chore: auto-save",
    max_display: int = DEFAULT_MAX_DISPLAY,
) -> str:
    """Build commit message from list of file paths.

    Format (filename-list since 2026-05-14):
        "{prefix} {basename(files[0])}, {basename(files[1])}, ..., +N more"
    or, when len(files) <= max_display:
        "{prefix} {basename(files[0])}, {basename(files[1])}, ..."

    Args:
        files: Iterable of file paths (absolute or relative).
        prefix: Commit message prefix (e.g. "chore: auto-save" / "chore: auto-commit").
        max_display: Max basenames to render before truncating to "+N more".

    Returns:
        Commit message string suitable for `git commit -m`.

    Examples:
        >>> format_commit_message(["a.py", "b.py"])
        'chore: auto-save a.py, b.py'
        >>> format_commit_message(["a.py", "b.py", "c.py", "d.py"])
        'chore: auto-save a.py, b.py, c.py +1 more'
        >>> format_commit_message(["a.py"], prefix="chore: auto-commit")
        'chore: auto-commit a.py'
    """
    files_list = list(files)
    count = len(files_list)
    if count == 0:
        return prefix
    head = ", ".join(os.path.basename(f) for f in files_list[:max_display])
    if count > max_display:
        head += f" +{count - max_display} more"
    return f"{prefix} {head}"
