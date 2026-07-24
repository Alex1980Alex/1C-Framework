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
import subprocess
import sys
from collections.abc import Iterable

DEFAULT_MAX_DISPLAY = 3

# A .git/index.lock older than this is treated as an orphan of a crashed /
# interrupted git process (live incident 2026-07-24: a 4.5-hour-old 0-byte
# lock from a dead auto-save run blocked every subsequent commit). Git itself
# never holds the index lock for minutes.
STALE_INDEX_LOCK_MAX_AGE_SEC = 600


def clear_stale_index_lock(
    project_root: str,
    max_age_sec: int = STALE_INDEX_LOCK_MAX_AGE_SEC,
) -> bool:
    """Remove .git/index.lock if it is older than max_age_sec.

    Returns True when a stale lock was removed. Fresh locks (a live git
    process) and any OS error leave the file alone — callers proceed and
    let git report the conflict normally.
    """
    import time

    lock_path = os.path.join(project_root, ".git", "index.lock")
    try:
        age = time.time() - os.path.getmtime(lock_path)
    except OSError:
        return False
    if age < max_age_sec:
        return False
    try:
        os.remove(lock_path)
        return True
    except OSError:
        return False


# Mirror of .pre-commit-config.yaml top-level `exclude:` for the .py-relevant
# trees — ruff-format must leave vendored / generated code alone (those carry
# their own lint configs).
_RUFF_SKIP_PREFIXES = (
    "tools/",
    "infra/",
    "external/",
    "cache/",
    "src/bsl/",
    "jre/",
    ".serena/",
    ".vscode-extensions/",
)


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


def get_amendable_head(
    project_root: str,
    prefix: str = "chore: auto-save",
    timeout: int = 5,
) -> list[str] | None:
    """Return HEAD's file list when HEAD can be absorbed via ``--amend``.

    Amend-absorb (2026-06-12, план из memory feedback-auto-git-save-preempt):
    consecutive auto-save'ы схлопываются в ОДИН коммит вместо стопки
    ``chore: auto-save`` — следующий auto-save амендит предыдущий. Побочный
    бонус: единственный незапушенный auto-save на вершине легко поглощается
    осмысленным коммитом обычным ``git commit --amend -m "feat: ..."``.

    Safety-гейты (любой не пройден → None → обычный новый коммит):
      1. subject HEAD начинается с ``prefix`` (строго тот же prefix —
         split-commit разделение auto-save/sweep-drift не смешивается);
      2. HEAD НЕ существует ни на одном remote (``git branch -r --contains``)
         — амендить запушенное нельзя, иначе divergence;
      3. нет merge/rebase in progress (MERGE_HEAD / rebase-merge / rebase-apply).

    Returns:
        Список путей файлов HEAD-коммита (для объединённого сообщения)
        или None, если амендить нельзя.
    """
    try:
        subject = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=project_root,
        )
        if subject.returncode != 0:
            return None
        subj = subject.stdout.strip()
        # Граница слова: "chore: auto-save foo.py" — да; осмысленный
        # "chore: auto-save amend support" тоже пройдёт (message-only risk,
        # review 2026-06-12 rec#1), но "chore: auto-saved..." — нет.
        if subj != prefix and not subj.startswith(prefix + " "):
            return None

        git_dir_r = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=project_root,
        )
        if git_dir_r.returncode != 0:
            return None
        git_dir = git_dir_r.stdout.strip()
        if not os.path.isabs(git_dir):
            git_dir = os.path.join(project_root, git_dir)
        for marker in (
            "MERGE_HEAD",
            "rebase-merge",
            "rebase-apply",
            "CHERRY_PICK_HEAD",
            "REVERT_HEAD",
        ):
            if os.path.exists(os.path.join(git_dir, marker)):
                return None

        pushed = subprocess.run(
            ["git", "branch", "-r", "--contains", "HEAD"],
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=project_root,
        )
        # rc!=0 (напр. пустой repo) или непустой вывод (есть на remote) → нельзя
        if pushed.returncode != 0 or pushed.stdout.strip():
            return None

        shown = subprocess.run(
            [
                "git",
                "-c",
                "core.quotepath=false",
                "show",
                "--pretty=format:",
                "--name-only",
                "HEAD",
            ],
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=project_root,
        )
        if shown.returncode != 0:
            return None
        return [line.strip() for line in shown.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, OSError):
        return None


def merge_for_message(head_files: Iterable[str], new_files: Iterable[str]) -> list[str]:
    """Union файлов HEAD + новых для объединённого commit message.

    Дедуп по basename (head хранит relative-пути, хуки могут давать absolute —
    один файл не должен дублироваться в сообщении; коллизия одноимённых файлов
    из разных каталогов затрагивает только текст сообщения, не содержимое).
    """
    seen: set[str] = set()
    out: list[str] = []
    for f in list(head_files) + list(new_files):
        key = os.path.basename(f).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _python_exe(project_root: str) -> str:
    """Return the project's .venv python (where ruff lives), or fall back to
    the interpreter running the hook."""
    for rel in (
        os.path.join(".venv", "Scripts", "python.exe"),
        os.path.join(".venv", "bin", "python"),
    ):
        cand = os.path.join(project_root, rel)
        if os.path.isfile(cand):
            return cand
    return sys.executable


def _ruff_line_length(project_root: str, default: int = 100) -> int:
    """Read ``[tool.ruff] line-length`` from pyproject.toml (default 100).

    Passed to ruff explicitly: a bare ``ruff format <file>`` does not reliably
    pick up the formatter line-length here, while ``--line-length N`` is
    verified-equivalent to the pre-commit ruff-format hook that CI runs.
    """
    try:
        import tomllib

        with open(os.path.join(project_root, "pyproject.toml"), "rb") as fh:
            data = tomllib.load(fh)
        value = data.get("tool", {}).get("ruff", {}).get("line-length")
        return int(value) if value else default
    except (OSError, ValueError, TypeError, KeyError, ImportError):
        return default


def format_staged_python(
    project_root: str,
    files: Iterable[str],
    timeout: int = 20,
) -> None:
    """Ruff-format the .py files about to be auto-committed, then re-stage them.

    Auto-commit bypasses pre-commit (``--no-verify`` / custom core.hooksPath),
    so unformatted .py would otherwise land in the repo and turn CI's pre-commit
    job red (memory ``project-ci-precommit-red-autocommit-noverify``). Running
    ruff-format here with the repo line-length keeps every auto-commit CI-clean.

    Best-effort: any failure (ruff missing, timeout) is swallowed — never raises
    and never blocks the commit. Vendored / generated trees are skipped to mirror
    the pre-commit top-level exclude.
    """
    root_norm = project_root.replace("\\", "/").rstrip("/")
    py: list[str] = []
    for f in files:
        norm = f.replace("\\", "/")
        if not norm.lower().endswith(".py"):
            continue
        rel = norm[len(root_norm) + 1 :] if norm.startswith(root_norm + "/") else norm
        if any(rel.startswith(p) for p in _RUFF_SKIP_PREFIXES):
            continue
        py.append(f)
    if not py:
        return
    cmd = [
        _python_exe(project_root),
        "-m",
        "ruff",
        "format",
        "--line-length",
        str(_ruff_line_length(project_root)),
        "--",
        *py,
    ]
    try:
        subprocess.run(cmd, timeout=timeout, capture_output=True, cwd=project_root)
        subprocess.run(
            ["git", "add", "--", *py],
            timeout=10,
            capture_output=True,
            cwd=project_root,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        # Never block the auto-commit on a formatting hiccup (ruff missing,
        # timeout, bad args). CI's pre-commit job remains the backstop.
        pass
